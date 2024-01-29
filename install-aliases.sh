#! /bin/sh

export OP25_HOME=`pwd`

grep 'OP25_HOME' ~/.bashrc || echo "export OP25_HOME=${OP25_HOME}" >> ~/.bashrc
grep 'op25-aliases.sh' ~/.bashrc || echo ". ${OP25_HOME}/op25-aliases.sh" >> ~/.bashrc
echo 'OP25 aliases will now be available from new shells. Run ". ~/.bashrc" for your op25 aliases to take effect in this shell'
