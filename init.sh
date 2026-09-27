
if [[ -z "${PUBLIC_USER}" ]]; then
  PUBLIC_USER="public_access"
fi

if [[ -z "${PUBLIC_PASSWORD}" ]]; then
  PUBLIC_PASSWORD="$(python3 -c "print(__import__('secrets').token_urlsafe(64))")"
  echo "Password for User $PUBLIC_USER: $PUBLIC_PASSWORD"
else
  echo "Public User name: $PUBLIC_USER"
fi

SCRIPT_PASSWORD="$(python3 -c "print(__import__('secrets').token_urlsafe(64))")"

# create user that pushes timetable to radicale
echo "$SCRIPT_PASSWORD" | htpasswd -5 -B -i -c /etc/radicale/htpasswd public
# create user to access timetable
echo "$PUBLIC_PASSWORD" | htpasswd -5 -B -i /etc/radicale/htpasswd "$PUBLIC_USER"

# set environment for update script
echo "CALDAV_USER=public
CALDAV_PASSWORD=$SCRIPT_PASSWORD" >> /courseapp/.env

echo "CALENDAR_URL=$CALENDAR_URL
#CALENDAR_PAGE_URL=$CALENDAR_PAGE_URL
#CALENDAR_PAGE_KEY=$CALENDAR_PAGE_KEY" >> /courseapp/.env

service radicale start

# wait for service startet
sleep 3

# run update ones manually
su courseapp -c "/bin/bash -c 'cd /courseapp/ && /courseapp/venv/bin/python /courseapp/calendar_parser.py'"
service cron start

sleep infinity