FROM apache/spark:3.5.0
USER root

RUN curl -L -o /opt/spark/jars/mongo-spark-connector_2.12-10.3.0.jar \
    https://repo1.maven.org/maven2/org/mongodb/spark/mongo-spark-connector_2.12/10.3.0/mongo-spark-connector_2.12-10.3.0.jar

RUN curl -L -o /opt/spark/jars/mongodb-driver-sync-5.2.0.jar \
    https://repo1.maven.org/maven2/org/mongodb/mongodb-driver-sync/5.2.0/mongodb-driver-sync-5.2.0.jar 
RUN    curl -L -o /opt/spark/jars/bson-5.2.0.jar \
    https://repo1.maven.org/maven2/org/mongodb/bson/5.2.0/bson-5.2.0.jar 
RUN    curl -L -o /opt/spark/jars/mongodb-driver-core-5.2.0.jar \
    https://repo1.maven.org/maven2/org/mongodb/mongodb-driver-core/5.2.0/mongodb-driver-core-5.2.0.jar 
RUN    curl -L -o /opt/spark/jars/bson-record-codec-5.2.0.jar \
    https://repo1.maven.org/maven2/org/mongodb/bson-record-codec/5.2.0/bson-record-codec-5.2.0.jar

COPY . /app
COPY *.jar /opt/spark/jars/

CMD ["/opt/spark/bin/spark-submit", "/app/spark_main.py"]