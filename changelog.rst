Changelog
=========

Release 0.3.10
--------------

- Fix: ``Options``: option values which contain space characters, single and double quotes are surrounded by double quotes now (`#87`_)

.. _#87: https://github.com/renskiy/fabricio/issues/87

Release 0.3.9
-------------

- Fix: ``StreamingReplicatedPostgresqlContainer`` aborts execution if master promotion failed with exception
- Enhancement: dangling volumes removal as default option of ``Container.delete()``

Release 0.3.8
-------------

- Fix: ``StreamingReplicatedPostgresqlContainer``: do not promote host without data as new master if there is another host with DB exists
- Enhancement: ``docker.Container``: added `safe_options` property which contains safe options; multiple containers with such options on the same host will not conflict

Release 0.3.7
-------------

- Change: add `--interactive` option every time when `--tty` has been used
- Enhancement: custom name can be assigned to the infrastructure
- Enhancement: ``PostgresqlContainer`` can be updated without new container creation if only configs were changed
- Enhancement: added ``StreamingReplicatedPostgresqlContainer`` which supports master-slave configuration deployment (`#72`_)
- Enhancement: added `example and recipes`_

.. _#72: https://github.com/renskiy/fabricio/issues/72
.. _example and recipes: examples/

Release 0.3.6
-------------

- Fix: set default env.infrastructure at the very first time
- Change: ``fabricio.run()`` use current host (instead of current infrastructure) to generate cache key
- Change: ``DjangoContainer`` doesn't call ``backup()`` before applying migrations now
- Change: ``PostgresqlContainer`` doesn't contain ``PostgresqlBackupMixin`` now
- Enhancement: use ``remote_tunnel`` only if registry hostname is IP or alias of the remote host itself (`#66`_)
- Enhancement: image, options and other container attributes now can be passed to the ``Container`` upon initialization

.. _#66: https://github.com/renskiy/fabricio/issues/66

Release 0.3.1
-------------

- Fix: fixed Fabric's ``serial`` and ``parallel`` decorators usage within ``Tasks``
- Change: removed deprecated ``CronContainer``
- Change: removed deprecated ``utils.yes()``
- Change: ``PostgresqlContainer``: deprecated 'postgresql_conf', 'pg_hba_conf' and 'data' properties in favour of new ones
- Change: ``PostgresqlBackupMixin``: deprecated 'db_backup_folder' and 'db_backup_name' properties in favour of new ones
- Change: ``PostgresqlBackupMixin``: removed ``db_backup_enabled`` flag
- Enhancement: ``fabricio.run()``: added 'use_cache=False' option which enables shared cache incapsulated within single infrastructure
- Enhancement: ``PostgresqlBackupMixin``: 'backup' and 'restore' cache result per infrastructure

Release 0.3
-----------

- Change: ``PostgresqlBackupMixin``: do actual backup only if ``db_backup_enabled`` is True
- Change: modified ``DockerTasks`` commands params order: force, tag, registry => tag, registry, force (`#52`_)
- Change: ``DockerTasks``: 'revert' command was removed from the list of available commands in favour of 'rollback'
- Change: ``tasks.infrastructure`` decorator does not require special environ variable to be autoconfirmed, instead special command '<infrastructure>.confirm' can be used for this purpose

.. _#52: https://github.com/renskiy/fabricio/issues/52

Release 0.2.17
--------------

- Fix: fixed bug when Container.update() changed container name

Release 0.2.16
--------------

- Fix: fixed Django migrations plan
- Fix: fixed Django migrations change detection

Release 0.2.14
--------------

- Change: ``tasks.DockerTasks.deploy()`` does not run ``backup`` task by default
- Enhancement: ``docker.Container.update()`` forces starting container if no changes detected
- Enhancement: ``apps.python.django.DjangoContainer.migrate()`` does not run ``migrate`` if actually no changes detected
- Enhancement: ``apps.python.django.DjangoContainer.migrate()`` calls ``backup()`` before applying migrations
- Enhancement: implemented ``apps.db.postgres.PostgresqlContainer.backup()`` and ``apps.db.postgres.PostgresqlContainer.restore()`` (`#17`_)
- Enhancement: Fabric's ``remote_tunnel`` has been muzzled and ``tasks.DockerTasks.pull()`` output enabled instead (`#42`_)

.. _#17: https://github.com/renskiy/fabricio/issues/17
.. _#42: https://github.com/renskiy/fabricio/issues/42

Release 0.2.13
--------------

- Enhancement: ``tasks.BuildDockerTasks.prepare()`` always uses ``docker build``'s --pull option

Release 0.2.12
--------------

- Fix: fixed Fabric's --display option (`#33`_)
- Enhancement: skip tasks which require host where last is not provided (`#45`_)

.. _#33: https://github.com/renskiy/fabricio/issues/33
.. _#45: https://github.com/renskiy/fabricio/issues/45
