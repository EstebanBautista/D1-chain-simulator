FROM nginx:alpine

# No user is added here: the nginx master process binds port 80, which needs
# root, and the official image already drops its worker processes to the
# unprivileged `nginx` user. The Python services run fully non-root.
#
# No build step: the dashboard is plain HTML, CSS and JavaScript, so a student
# can open any file and read exactly what runs in the browser.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css charts.js app.js /usr/share/nginx/html/

EXPOSE 80
