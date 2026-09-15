
.. _bash_completion:

How to set up bash completion
=============================

When using bash as your shell, ``testrunner`` can use argcomplete
(https://kislyuk.github.io/argcomplete/) for auto-completion.
For this ``argcomplete`` needs to be installed **and** enabled.

Install argcomplete using:

.. code-block:: bash

    sudo pip install 'argcomplete>=0.5.7'

For global activation of all argcomplete enabled python applications run:

.. code-block:: bash

    sudo activate-global-python-argcomplete

For permanent (but not global) ``testrunner`` activation, use:

.. code-block:: bash

    register-python-argcomplete testrunner >> ~/.bashrc

For one-time activation of argcomplete for ``testrunner`` only, use:

.. code-block:: bash

    eval "$(register-python-argcomplete testrunner)"
