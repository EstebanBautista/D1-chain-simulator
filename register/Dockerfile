FROM python:3.12-slim

# This image runs nginx, whose master process binds port 80 and therefore
# needs root; the workers drop to an unprivileged user on their own. The
# Python services (backend, gateway, forwarder, central API) run fully
# non-root.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# nginx turns the register into the entry point to the store's web site.
# curl, ping and dig let the student inspect connectivity by hand from inside
# the register.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        curl \
        iputils-ping \
        dnsutils \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The register has NO internet access: it sits on its store's internal network,
# which is what a real store's register looks like. Every dependency must
# therefore be declared HERE and installed at image build time. You cannot
# install anything inside a running register — the attempt will simply fail to
# reach the network, which is the intended behaviour, not a broken environment.
#
# Later phases give the register local storage. Add SQLite and anything else it
# needs here:
#
#   RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 \
#       && rm -rf /var/lib/apt/lists/*

COPY nginx.conf.template /etc/nginx/templates/register.conf.template
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY integration_tests.py .

EXPOSE 80

# The entrypoint renders register-config.js and the nginx
# upstream, then hands over to nginx. nginx
# stays in the foreground, which also keeps the container alive for
# `make shell CONTAINER=store-1-register-1`.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
