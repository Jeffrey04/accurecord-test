# Accurecord Test

## Prerequisite

* uv
* podman / docker
* Python 3.11


## Getting started

You can get the project running with docker-compose, it will pull the latest image from GitHub

```
podman compose up
```

By default the application should be running at port 8080, it can be overriden by specifying the environment `WEB_PORT` in the docker compose, remember to adjust the exposed port as well

### Database initialization

After the container is up, head into the image

```
podman exec -it <container name> sh
```

Then attempt to execute the schema SQL

```
sqlite3 database.sqlite < database/schema.sql
```

Sometimes you may get error saying database is locked, just remove the database and reattempt

```
rm -rf database.sqlite*
touch database.sqlite
sqlite3 database.sqlite < database/schema.sql
```

## Running test

```
make test
```