# Only this reviewed recipe, runtime and hash-locked npm manifests are inputs.
# No candidate source or npm configuration executes during network preparation.
FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json /opt/atenea-web-deps/
RUN cd /opt/atenea-web-deps \
    && npm ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org \
    && chmod -R a+rX /opt/atenea-web-deps \
    && touch /opt/atenea-npm-globalrc
COPY atenea-web-runtime-v1.py /opt/atenea-web-runtime-v1.py
ENV HOME=/work/home
ENV PATH=/usr/local/bin:/usr/bin:/bin
ENV npm_config_offline=true
ENV npm_config_audit=false
ENV npm_config_fund=false
ENV npm_config_userconfig=/dev/null
ENV npm_config_globalconfig=/opt/atenea-npm-globalrc
WORKDIR /work
USER 1000:0
CMD ["/bin/sleep", "infinity"]
