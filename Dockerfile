FROM odoo:17.0

USER root

# Install system dependencies required for compiling custom python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjq-dev \
    python3-dev \
    wget \
    git \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY ./requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# --- OpenG2P addon repos: cloned from GitHub, pinned for reproducibility ---
# Override any pin at build time with --build-arg.
ARG OPENG2P_REGISTRY_REF=v1.5.10
ARG OPENG2P_SOCIAL_REGISTRY_REF=v1.5.8
# community-addons has no release tag; pin to the tested commit on 17.0-develop
ARG OPENG2P_COMMUNITY_REF=6ab9227081f12d6b7a836aef4e193a37813bd22c
ARG OPENG2P_ATI_REF=develop
# All four addon repos are PUBLIC on GitHub — no token/BuildKit secret required.

RUN git clone --depth 1 --branch "$OPENG2P_REGISTRY_REF" \
        https://github.com/OpenG2P/openg2p-registry /mnt/openg2p-registry \
    && git clone --depth 1 --branch "$OPENG2P_SOCIAL_REGISTRY_REF" \
        https://github.com/OpenG2P/openg2p-social-registry /mnt/openg2p-social-registry \
    && git clone https://github.com/OpenG2P/openg2p-social-registry-community-addons /mnt/openg2p-community-addons \
    && git -C /mnt/openg2p-community-addons checkout "$OPENG2P_COMMUNITY_REF" \
    && git clone --depth 1 --branch "$OPENG2P_ATI_REF" \
        https://github.com/Centre-for-Open-Societal-Systems/OAN_Registries /mnt/openg2p-ati \
    && find /mnt/openg2p-registry /mnt/openg2p-social-registry \
        /mnt/openg2p-community-addons /mnt/openg2p-ati \
        -maxdepth 1 -name .git -prune -exec rm -rf {} +

# Install the cloned addon repos' Python requirements (module external_dependencies:
# jq, fastapi, extendable(-pydantic), pydantic, jwcrypto, python-jose, PyLD, boto3, ...)
RUN pip3 install --no-cache-dir \
    -r /mnt/openg2p-registry/requirements.txt \
    -r /mnt/openg2p-social-registry/requirements.txt \
    -r /mnt/openg2p-community-addons/requirements.txt

# Bake config and project addons into the image.
COPY ./config /etc/odoo
COPY ./addons /mnt/extra-addons
COPY ./custom_addons /opt/extra-addons

# Filestore / data dir (persist with a named volume in production)
RUN mkdir -p /var/lib/odoo && chown -R odoo:odoo /var/lib/odoo /etc/odoo /mnt
VOLUME ["/var/lib/odoo"]

USER odoo

EXPOSE 8069

# NOTE: this image does NOT include Postgres. It will not auto-connect to a DB.
# The odoo:17.0 base entrypoint reads these env vars to build the connection:
#   HOST (db hostname)  PORT (default 5432)  USER  PASSWORD
# Supply them at runtime, e.g.:
#   docker run -p 8069:8069 \
#     -e HOST=my-pg-host -e USER=odoo -e PASSWORD=secret \
#     -v odoo-web-data:/var/lib/odoo odoo-prod:17
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo", "-c", "/etc/odoo/odoo.conf"]