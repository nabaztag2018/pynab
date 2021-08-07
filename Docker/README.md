# Docker-based development environment

This folder contains a Docker Compose environment to develop for Pynab on a PC,
rather than on the Raspberry Pi.

## How to (tl;dr)

All commands must be run from the `Docker/` directory.

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

The following containers are started (See [docker-compose.yml](docker-compose.yml))
- `db`: PostgreSQL database, with automatic creation of the `pynab` user and
  database.
- `pynab`: First runs `manage.py migrate` to apply DB migrations
  and `manage.py compilemessages` to update localization messages,
  then runs Nabd (with NabIOVirtual interface), the nab.*d services,
  and web interface WSGI.

`db` uses the official PostgreSQL image. `pynab` uses a custom image
based on the official Python image (See [nab/Dockerfile](nab/Dockerfile)).

To access NabIOVirtual, you can connect over TCP on port 10544:
```
nc 127.0.0.1 10544
```

This interface currently displays LEDs and sounds.

### Access to the database

Containers access the database via a Unix socket inside a shared volume
(mounted in `/var/run/postgresql/`). This is atypical (usually services would
connect to the DB via the network), but it allows the environment to work
without having to modify Pynab which assumes socket-based DB communication.

### Host volume

The pynab project directory is shared via a host volume, mounted in
`/home/pi/pynab` inside the containers to replicate the Raspberry Pi location.

### Synchronization between containers

Containers have dependencies: The individual services cannot start until the
database is initialized, and the Pynab container cannot start until
PostgreSQL is up and running and the `pynab` database exists.

Synchronization is currently crudely achieved via a shell script:
- `wait-for-db.sh`: Waits for the database to be available. This waits for the
  `pynab` database to be available, as just waiting for PostgreSQL to be running
  is not enough.

