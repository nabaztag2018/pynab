# Docker-based development environment

This folder contains a Docker Compose environment to develop for pynab on a PC,
rather than on the Raspberry Pi.

## How to (tl;dr)

All commands must be run inside the `Docker/` folder.

Start everything:

```
docker-compose up --build -d
# Visit http://localhost:8000
```

View logs:

```
docker-compose logs -f
```

Stop everything:

```
docker-compose down
```

## Details

### Containers

The following containers are started (See
[docker-compose.yml](docker-compose.yml))
- `db`: PostgreSQL database, with automatic creation of the `pynab` user and
  database.
- `migrate`: Runs `manage.py migrate` to apply DB migrations.
- `nabweb`: Web interface WSGI.
- `nab*d`: One container for each service.
- `nabdevd`: A dummy nabd replacement, since all services need to talk to nabd
  but it cannot run without the real hardware.

`db` is using the official PostgreSQL image. `nabdevd` is using a publicly
available custom container. All other containers are using a custom image based
on the official Python image (See [nab/Dockerfile](nab/Dockerfile)).

The dummy nabd daemon is a
[separate open-source project](https://gitlab.com/nguillaumin/nabdevd). It's
quite minimal for now but will be extended to simulate as many functions
provided by nabd as possible.

### Access to the database

All containers access the database via a Unix socket inside a shared volume
(mounted in `/var/run/postgresql/`). This is atypical (usually services would
connect to the DB via the network), but it allows the environment to work
without having to modify pynab which assumes socket-based DB communication.

### Host volume

The pynab project folder is shared via a host volume, mounted in
`/home/pi/pynab` inside the containers to replicate the Raspberry Pi location.

### Synchronization between containers

Containers have dependencies: The individual services cannot start until the
database is initialized, and the migration container cannot start until
PostgreSQL is up and running and the `pynab` database exists.

Synchronization is currently crudely achieved via shell scripts:
- `wait-for-db.sh`: Waits for the database to be available. This wait for the
  `pynab` database to be available, as just waiting for PostgreSQL to be running
  is not enough.
- `wait-for-file.sh`: Waits for a specific file to appear. This is used by the
  migration container which writes a file when the migrations are completed to
  let the services now the database is ready. The file is written under
  `/var/run/postgresql/`, a shared folder across containers. Unfortunately all
  containers must run as root in order to be able to write into this folder.
