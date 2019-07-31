FROM ppdli-base

LABEL version="0.0.1"
LABEL maintainer="Frank Martin <f.martin@iknl.nl>"

ARG port=80
EXPOSE ${port}
ENV PROXY_SERVER_PORT ${port}

COPY /joey/node/startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh

WORKDIR /
ENTRYPOINT [ "/usr/local/bin/startup.sh" ]