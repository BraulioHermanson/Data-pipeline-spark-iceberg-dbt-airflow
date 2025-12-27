#!/bin/bash
set -e

case "$SPARK_MODE" in
  master)
    exec /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master \
      --host $SPARK_MASTER_HOST --port $SPARK_MASTER_PORT --webui-port $SPARK_MASTER_WEBUI_PORT
    ;;
  worker)
    exec /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker \
      --webui-port 8081 $SPARK_MASTER_URL
    ;;
  *)
    exec "$@"
    ;;
esac
