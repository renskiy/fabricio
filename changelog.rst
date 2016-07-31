Changelog
=========

Release 0.2.14
--------------

Enhancement: :code:`docker.Container.update()` forces starting container if no changes detected

Release 0.2.13
--------------

Enhancement: :code:`tasks.BuildDockerTasks.prepare()` always uses :code:`docker build`'s --pull option

Release 0.2.12
--------------

Fix: Fixed Fabric's --display option (`#33`_)
Enhancement: Skip tasks which require host where last is not provided (`#45`_)

.. _#33: https://github.com/renskiy/fabricio/issues/33
.. _#45: https://github.com/renskiy/fabricio/issues/45
