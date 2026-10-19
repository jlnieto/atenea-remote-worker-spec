#!/usr/bin/env python3
"""Private, fixed-action operator recovery, independent of Spring and its DB auth.

Loaded only by the root-owned release executor. No public listener, shell,
caller-selected target, restore, version change or general-purpose proxy.
"""
from __future__ import annotations
import contextlib
import hashlib
import html
import http.server
import json
import selectors
import subprocess
import threading
import time
import urllib.parse
import uuid
from pathlib import Path

CONFIG = Path("/etc/atenea-release-v1/rescue.json")
PROTOCOL = "atenea-rescue/v1"
ADDRESS = ("127.0.0.1", 8792)
ACTIVE = {"ACCEPTED", "APPLYING", "ATTENTION"}
STYLE = "body{font:17px system-ui;max-width:42rem;margin:auto;padding:1rem;background:#f6f7fb;color:#172136}h1{font-size:1.6rem}h2{margin-top:1.8rem}section{background:white;border:1px solid #cbd2df;border-radius:.7rem;padding:1rem;margin:1rem 0}button,a{font:inherit;min-height:48px}button{width:100%;padding:.7rem;margin:.4rem 0;border:1px solid #385489;border-radius:.5rem;background:white;color:#172136}p{line-height:1.5;overflow-wrap:anywhere}a{display:inline-block;padding:.4rem 0}"


def configuration(r):
    value=json.loads(r.trusted(CONFIG,0o600).read_bytes())
    r.exact(value,{"protocol","allowedLogin","origin"})
    if (value["protocol"] != PROTOCOL or not isinstance(value["allowedLogin"],str)
            or not r.re.fullmatch(r"[a-zA-Z0-9._+@-]{3,200}",value["allowedLogin"])
            or not isinstance(value["origin"],str)
            or not r.re.fullmatch(r"https://[a-z0-9-]+\.[a-z0-9-]+\.ts\.net:8443",value["origin"])):
        raise r.Rejected("RESCUE_AUTHORITY_INVALID")
    return value


class Rescue:
    def __init__(self,r,controller,config):
        self.r,self.controller,self.config=r,controller,config
        self.root=controller.root/"rescue"

    def path(self,identifier):
        return self.root/(self.r.identity(identifier)+".json")

    def read(self,identifier):
        return json.loads(self.r.trusted(self.path(identifier),0o600).read_bytes())

    def records(self):
        if not self.root.exists():return []
        self.r.trusted_directory(self.root,0o700)
        paths=list(self.root.iterdir())
        if len(paths)>1000:raise self.r.Rejected("RESCUE_EVIDENCE_BOUND")
        return [self.read(path.stem) for path in paths]

    def require_settled(self):
        if any(record["state"] in ACTIVE for record in self.records()):
            raise self.r.Rejected("RESCUE_REQUIRES_INSPECTION")

    @staticmethod
    def public(record):
        return {key:record.get(key) for key in ("protocol","operationId","state","sourceCommit",
                "createdAt","finishedAt","errorCode")}

    def summary(self):
        target=self.controller.targets["APP_PROD"]
        try:
            observed=target.observe_current()
            app={key:observed[key] for key in ("sourceCommit","healthy")}
        except Exception:
            app={"healthy":False,"errorCode":"APP_OBSERVATION_UNAVAILABLE"}
        try:
            worker=target.worker_health()
            worker={"healthy":True,"idle":True,"projectCodexV4":"project-codex-v4" in worker["capabilities"]}
        except Exception:
            worker={"healthy":None,"idle":None,"errorCode":"WORKER_UNAVAILABLE_OR_BUSY"}
        return {"protocol":PROTOCOL,"app":app,"worker":worker,
            "operations":[self.public(record) for record in sorted(self.records(),key=lambda v:v["createdAt"],reverse=True)[:10]]}

    def snapshot(self):
        r=self.r;target=self.controller.targets["APP_PROD"]
        backend=json.loads(r.command(["/usr/bin/docker","inspect","atenea-backend-prod"],timeout=5))[0]
        postgres=json.loads(r.command(["/usr/bin/docker","inspect","atenea-postgres-prod"],timeout=5))[0]
        image=json.loads(r.command(["/usr/bin/docker","image","inspect",backend["Image"]],timeout=5))[0]
        effective=json.loads(r.command(target.compose("config","--format","json"),timeout=10))
        labels=backend["Config"].get("Labels") or {}
        source=(image["Config"].get("Labels") or {}).get("org.opencontainers.image.revision")
        if (labels.get("com.docker.compose.project") != effective.get("name")
                or labels.get("com.docker.compose.service") != "atenea-backend-prod"
                or not isinstance(source,str) or not r.HEX.fullmatch(source)
                or image["Id"] != backend["Image"] or not postgres["State"]["Running"]
                or labels.get("org.opencontainers.image.revision",source) != source):
            raise r.Rejected("RESCUE_IDENTITY_CHANGED")
        return {"containerId":backend["Id"],"imageId":backend["Image"],"sourceCommit":source,
            "postgresId":postgres["Id"],"postgresMountsSha256":r.digest(postgres["Mounts"]),
            "composeSha256":r.digest(effective),"startedAt":backend["State"]["StartedAt"],
            "running":backend["State"]["Running"],"restarting":backend["State"]["Restarting"]}

    def require_idle(self):
        # Fixed read-only SQL. The common advisory lock is held through the
        # restart; all App admissions use the same lock (V84/V86/V89/V99).
        query="""BEGIN READ ONLY; SET LOCAL statement_timeout='5s';
SELECT json_build_object(
 'schema',(SELECT max(version::int) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'),
 'flywayFailures',(SELECT count(*) FROM flyway_schema_history WHERE NOT success),
 'runs',(SELECT count(*) FROM agent_run WHERE status NOT IN ('SUCCEEDED','FAILED','CANCELLED')),
 'validations',(SELECT count(*) FROM validation_operation WHERE status='RUNNING'),
 'publications',(SELECT count(*) FROM mobile_delivery_operation WHERE kind='RELEASE' AND state NOT IN ('SUCCEEDED','ROLLED_BACK','FAILED','BLOCKED')),
 -- These two states are completed source preparations, not running work.
 -- Preserve them and their receipts; unknown/new states still block admission.
 'updates',(SELECT count(*) FROM mobile_source_update_operation WHERE state NOT IN
    ('PUBLISHED','FAILED','BLOCKED','RESOLVER_COMPLETED','READY_TO_FINALIZE')),
 'repairs',(SELECT count(*) FROM mobile_validation_recovery WHERE kind='REPAIR' AND state IN ('PREPARE_REQUESTED','PREPARING','APPLY_REQUESTED','APPLYING','ATTENTION'))); ROLLBACK;"""
        raw=self.r.command(self.psql(),input=query.encode(),timeout=10)
        value=json.loads(raw)
        if value.get("schema",0)<99 or any(value.get(key)!=0 for key in
                ("flywayFailures","runs","validations","publications","updates","repairs")):
            raise self.r.Rejected("RESCUE_WORK_ACTIVE_OR_SCHEMA_UNSUPPORTED")
        self.controller.targets["APP_PROD"].worker_health()
        for path in (self.controller.root/"plans").glob("*/operation.json"):
            record=json.loads(self.r.trusted(path,0o600).read_bytes())
            if record["state"] in {"PREPARING","ROLLBACK_FAILED"} or (record["operationId"] and record["state"] not in self.r.TERMINAL):
                raise self.r.Rejected("RELEASE_IN_PROGRESS")

    @staticmethod
    def psql():
        return ["/usr/bin/docker","exec","-i","atenea-postgres-prod","/bin/sh","-c",
                'exec psql -X -U "$POSTGRES_USER" -d atenea_prod -qAt -v ON_ERROR_STOP=1']

    @contextlib.contextmanager
    def admission(self):
        process=subprocess.Popen(self.psql(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8"},bufsize=0)
        try:
            process.stdin.write(b"BEGIN; SET LOCAL lock_timeout='5s'; SET LOCAL idle_in_transaction_session_timeout='180s'; SELECT pg_advisory_xact_lock(814205002); SELECT 'LOCKED';\n")
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                deadline=time.monotonic()+10;output=b""
                while b"LOCKED\n" not in output:
                    if time.monotonic()>deadline or not selector.select(1):
                        if time.monotonic()>deadline:raise self.r.Rejected("RESCUE_ADMISSION_UNAVAILABLE")
                        continue
                    block=process.stdout.read(128)
                    if not block:raise self.r.Rejected("RESCUE_ADMISSION_UNAVAILABLE")
                    output+=block
                    if len(output)>256:raise self.r.Rejected("RESCUE_ADMISSION_UNAVAILABLE")
            yield process
        finally:
            if process.poll() is None:
                try:process.stdin.write(b"ROLLBACK;\n\\q\n");process.stdin.close();process.wait(timeout=3)
                except (OSError,subprocess.TimeoutExpired):process.kill();process.wait(timeout=3)
            if process.stdout:process.stdout.close()

    def plan(self,identifier):
        with self.controller.lock:
            if self.path(identifier).exists():return self.public(self.read(identifier))
            self.require_settled()
            if not self.controller.execution_lock.acquire(blocking=False):raise self.r.Rejected("RELEASE_IN_PROGRESS")
            try:
                with self.admission():
                    self.require_idle();before=self.snapshot()
                record={"protocol":PROTOCOL,"operationId":identifier,"state":"READY","sourceCommit":before["sourceCommit"],
                    "predecessor":before,"createdAt":int(time.time()),"expiresAt":int(time.time())+300,
                    "finishedAt":None,"errorCode":None,"restartAcknowledged":False,
                    "operatorSha256":hashlib.sha256(self.config["allowedLogin"].encode()).hexdigest()}
                self.r.save(self.path(identifier),record)
                return self.public(record)
            finally:self.controller.execution_lock.release()

    def execute(self,identifier):
        with self.controller.lock:
            record=self.read(identifier)
            if record["state"] != "READY":return self.public(record)
            if record["operatorSha256"]!=hashlib.sha256(self.config["allowedLogin"].encode()).hexdigest():
                raise self.r.Rejected("RESCUE_OPERATOR_CHANGED")
            self.require_settled()
            if record["expiresAt"]<=int(time.time()):raise self.r.Rejected("PLAN_EXPIRED")
            if not self.controller.execution_lock.acquire(blocking=False):raise self.r.Rejected("RELEASE_IN_PROGRESS")
            try:
                record["state"]="ACCEPTED";self.r.save(self.path(identifier),record)
                threading.Thread(target=self.restart,args=(record,),daemon=False).start()
            except Exception:
                self.controller.execution_lock.release();raise
            return self.public(record)

    def restart(self,record):
        try:
            with self.admission() as connection:
                self.require_idle()
                before=self.snapshot()
                if before!=record["predecessor"]:raise self.r.Rejected("RESCUE_IDENTITY_CHANGED")
                record["state"]="APPLYING";self.r.save(self.path(record["operationId"]),record)
                if connection.poll() is not None:raise self.r.Rejected("RESCUE_ADMISSION_LOST")
                args=["/usr/bin/docker","restart","--time","15",before["containerId"]] if before["running"] else ["/usr/bin/docker","start",before["containerId"]]
                self.r.command(args,timeout=45)
                record["restartAcknowledged"]=True;self.r.save(self.path(record["operationId"]),record)
                for attempt in range(30):
                    if connection.poll() is not None:raise self.r.Rejected("RESCUE_ADMISSION_LOST")
                    current=self.snapshot()
                    if any(current[key]!=before[key] for key in before if key not in {"startedAt","running","restarting"}):
                        raise self.r.Rejected("RESCUE_IDENTITY_CHANGED")
                    observation=self.controller.targets["APP_PROD"].observe_current()
                    if observation["healthy"] and current["running"] and not current["restarting"] and current["startedAt"]!=before["startedAt"]:
                        self.require_idle();record["state"]="SUCCEEDED";break
                    time.sleep(2)
                else:raise self.r.Rejected("RESCUE_HEALTH_FAILED")
        except Exception as error:
            record.update(state="ATTENTION" if record["state"]=="APPLYING" else "BLOCKED",
                errorCode=error.code if isinstance(error,self.r.Rejected) else "RESCUE_RESTART_UNCERTAIN")
        finally:
            record["finishedAt"]=int(time.time());self.r.save(self.path(record["operationId"]),record)
            self.controller.execution_lock.release()

    def inspect(self,identifier):
        with self.controller.lock:
            record=self.read(identifier)
            # Observation never starts/repeats an effect. On lost acknowledgement,
            # only a changed start time, same identities and healthy App can settle it.
            if record["state"] in ACTIVE and self.controller.execution_lock.acquire(blocking=False):
                try:
                    current=self.snapshot();before=record["predecessor"]
                    same=all(current[key]==before[key] for key in before if key not in {"startedAt","running","restarting"})
                    if record["state"]=="ACCEPTED" and current==before:
                        record.update(state="BLOCKED",errorCode="RESCUE_RESTART_NOT_STARTED",finishedAt=int(time.time()))
                        self.r.save(self.path(identifier),record)
                    elif (same and not current["restarting"] and current["running"] and current["startedAt"]!=before["startedAt"]
                            and self.controller.targets["APP_PROD"].observe_current()["healthy"]):
                        record.update(state="SUCCEEDED",errorCode=None,finishedAt=int(time.time()))
                        self.r.save(self.path(identifier),record)
                    elif same and not current["restarting"] and record.get("restartAcknowledged") is True:
                        record.update(state="FAILED",errorCode=record["errorCode"] or "RESCUE_HEALTH_FAILED",finishedAt=int(time.time()))
                        self.r.save(self.path(identifier),record)
                finally:self.controller.execution_lock.release()
            return self.public(record)


def handler(rescue):
    sessions={};lock=threading.Lock()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def authorize(self):
            login=self.headers.get_all("Tailscale-User-Login",[])
            if (self.client_address[0]!="127.0.0.1" or login!=[rescue.config["allowedLogin"]]
                    or self.headers.get_all("Host")!=[urllib.parse.urlparse(rescue.config["origin"]).netloc]):
                raise rescue.r.Rejected("RESCUE_OPERATOR_REQUIRED")
        def page(self,notice=""):
            status=rescue.summary();nonce=uuid.uuid4().hex;now=time.monotonic()
            with lock:
                for key in list(sessions):
                    if sessions[key]["expires"]<now:sessions.pop(key)
                if len(sessions)>=128:raise rescue.r.Rejected("RESCUE_SESSION_BOUND")
                sessions[nonce]={"expires":now+600,"planId":str(uuid.uuid4())}
            esc=lambda value:html.escape(str(value),quote=True)
            form=lambda action,label,identifier="":('<form method="post" action="/action"><input type="hidden" name="csrf" value="'+nonce+'">'
                +'<input type="hidden" name="action" value="'+action+'"><input type="hidden" name="operationId" value="'+esc(identifier)+'"><button>'+label+'</button></form>')
            content='<h1>Rescate de Atenea</h1><p>Acceso privado. Funciona sin iniciar sesión en Atenea.</p><p>'+esc(notice)+'</p>'
            content+='<h2>Estado</h2><p>App: '+('sana' if status["app"].get("healthy") else 'necesita atención')+'</p>'
            content+='<p>AX42: '+('sano y libre' if status["worker"].get("healthy") else 'ocupado o no verificable')+'</p><a href="/">Consultar estado</a>'
            content+='<h2>Recuperar App</h2><p>Reiniciar únicamente el backend, sin cambiar versión, datos, APK ni Codex. Primero se comprueba que no hay trabajo activo; después debes confirmar.</p>'
            content+=form("prepare","Comprobar y preparar reinicio")
            labels={"READY":"Preparado: falta tu confirmación","ACCEPTED":"Trabajando: espera","APPLYING":"Trabajando: espera",
                "SUCCEEDED":"Completado y sano","FAILED":"Reinicio terminado sin recuperar salud: requiere diagnóstico",
                "BLOCKED":"Bloqueado antes del efecto","ATTENTION":"Necesita comprobación; no se reintentará"}
            for record in status["operations"]:
                content+='<section><h3>'+esc(labels.get(record["state"],record["state"]))+'</h3><p>Versión conservada: '+esc(record["sourceCommit"][:12])+'</p>'
                if record["errorCode"]:content+='<p>Código: '+esc(record["errorCode"])+'</p>'
                if record["state"]=="READY":content+=form("confirm","Confirmo reiniciar sólo App PROD",record["operationId"])
                content+=form("inspect","Consultar esta misma operación",record["operationId"])+"</section>"
            content+='<p>No restaura bases de datos ni desbloquea permisos. Si el host o Tailscale están caídos, necesitas el acceso de emergencia al proveedor.</p>'
            body=('<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rescate Atenea</title><style>'+STYLE+'</style><body>'+content+'</body></html>').encode()
            self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
            import base64
            css_hash=base64.b64encode(hashlib.sha256(STYLE.encode()).digest()).decode()
            self.send_header("Content-Security-Policy","default-src 'none'; style-src 'sha256-"+css_hash+"'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Referrer-Policy","no-referrer");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            try:
                self.authorize()
                if self.path!="/":raise rescue.r.Rejected("CLOSED_REQUEST_REQUIRED")
                self.page()
            except Exception:self.send_error(403,"Private operator access required")
        def do_POST(self):
            try:self.authorize()
            except Exception:
                self.send_error(403,"Private operator access required");return
            try:
                if (self.path!="/action" or self.headers.get_all("Origin")!=[rescue.config["origin"]]
                        or self.headers.get("Content-Type")!="application/x-www-form-urlencoded"
                        or self.headers.get("Transfer-Encoding") is not None
                        or len(self.headers.get_all("Content-Length",[]))!=1):raise rescue.r.Rejected("CLOSED_REQUEST_REQUIRED")
                length=int(self.headers["Content-Length"])
                if not 0<length<=1024:raise rescue.r.Rejected("CLOSED_REQUEST_REQUIRED")
                fields=urllib.parse.parse_qs(self.rfile.read(length).decode("ascii"),strict_parsing=True,keep_blank_values=True,max_num_fields=3)
                if set(fields)!={"csrf","action","operationId"} or any(len(value)!=1 for value in fields.values()):raise rescue.r.Rejected("CLOSED_REQUEST_REQUIRED")
                csrf,action,identifier=(fields[key][0] for key in ("csrf","action","operationId"))
                with lock:session=sessions.get(csrf)
                if session is None or session["expires"]<time.monotonic():raise rescue.r.Rejected("RESCUE_CONFIRMATION_EXPIRED")
                if action=="prepare" and identifier=="":rescue.plan(session["planId"])
                elif action=="confirm":rescue.execute(identifier)
                elif action=="inspect":rescue.inspect(identifier)
                else:raise rescue.r.Rejected("CLOSED_REQUEST_REQUIRED")
                self.page("Resultado guardado. Consultar no vuelve a ejecutar la operación.")
            except rescue.r.Rejected as error:self.page("Operación detenida: "+error.code+". No repitas a ciegas.")
            except Exception:self.send_error(400,"Closed request required")
    return Handler


def start(r,controller):
    config=configuration(r)
    rescue=Rescue(r,controller,config)
    server=http.server.ThreadingHTTPServer(ADDRESS,handler(rescue))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return rescue
