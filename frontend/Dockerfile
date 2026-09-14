FROM nginx:alpine

# No user is added here: the nginx master process binds port 80, which needs
# root, and the official image already drops its worker processes to the
# unprivileged `nginx` user. The Python services run fully non-root instead.
#
# No build step: the site is plain HTML, CSS and JavaScript, so a student can
# open any file and read exactly what runs in the browser.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY index.html styles.css app.js /usr/share/nginx/html/

EXPOSE 80
