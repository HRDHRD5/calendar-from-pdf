FROM debian:13

# installing dependent packages
RUN apt-get -y --fix-missing update && apt-get -y upgrade \
    && apt-get -y install \
    cron \
    curl \
    radicale \
    apache2-utils \
    python3 \
    python3-pip \
    python3-venv \
    python3-bcrypt \
    python-is-python3

# Create parser Script user
RUN mkdir -p /courseapp/
RUN groupadd -g 6969 courseapp && useradd -u 6969 -g courseapp -M courseapp
RUN chown -R courseapp:courseapp /courseapp/
RUN usermod -d /courseapp/ courseapp

# copy script files into container
COPY --chown=courseapp:courseapp requirements.txt calendar_parser.py init.sh /courseapp/.
COPY --chown=courseapp:courseapp .env.SAMPLE /courseapp/.env
RUN chmod 500 /courseapp/init.sh

# Create python environment and cron job
RUN python3 -m venv /courseapp/venv
RUN /courseapp/venv/bin/pip install -r /courseapp/requirements.txt
RUN echo "0 * * * * cd /courseapp/ && /courseapp/venv/bin/python /courseapp/calendar_parser.py" | crontab -u courseapp -

# setup radicale
COPY --chown=radicale:radicale radicale.conf /etc/radicale/config
COPY --chown=radicale:radicale radicale_rights.conf /etc/radicale/rights

RUN mkdir -p /var/lib/radicale/collections && chown -R radicale:radicale /var/lib/radicale/collections && chmod -R o= /var/lib/radicale/collections
RUN touch /etc/radicale/htpasswd
RUN chown radicale:radicale /etc/radicale/htpasswd
RUN chmod 400 /etc/radicale/htpasswd

# create radicale service
RUN curl -o /etc/systemd/system/radicale.service https://raw.githubusercontent.com/Kozea/Radicale/refs/heads/master/contrib/systemd/radicale.service

CMD ["bash", "-c", "/courseapp/init.sh"]