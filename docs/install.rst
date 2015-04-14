
Install
=======

The Python module can be installed using ``pip``. It is also possible to
install a specific tag or branch by appending the name to the Git URL (e.g.
append ``@v0.1`` to get the tag ``v0.1``). This will typically require ``root``
permission.

.. code-block:: shell

    $ pip install git+ssh://git@github.com/zhanglab/model_script.git

Another option is to use ``virtualenv``. First set up a new environment in the
project directory, and activate it.

.. code-block:: shell

    $ virtualenv env
    $ . env/bin/activate

Now the Python module can be installed in the virtual environment using the
``pip`` command without requiring ``root`` permissions. When returning to the
project, simply reactivate the environment by running the second command.

The Cplex Python bindings will have to be installed manually in the virtual
environment as well. This should be done after activating the virtual
environment.

1. Go to the Cplex install directory: ``cd /path/to/Cplex``
2. Go to the appropriate subdirectory based on your platform:
   ``cd cplex/python/<platform>``
3. Run ``./setup.py install``

Dependencies
------------

- Linear programming solver (*Cplex*, *QSopt_ex*)
- PyYAML (for reading the native model format)
- Numpy (optional; model matrix can be exported to Numpy matrix if available)

There are no strictly required dependencies but most analyses rely on a linear
programming (LP) solver. The LP solver *Cplex* is the preferred solver.
The rational solver *QSopt_ex* is also supported (through `python-qsoptex`_).

.. _python-qsoptex: https://github.com/jonls/python-qsoptex