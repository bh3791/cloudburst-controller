import time
from kubernetes import client, config, watch
import mysql.connector
from mysql.connector import Error


# attempt to load in-cluster config, or else it's a docker setup
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
# load batch API
batch_v1 = client.BatchV1Api()
w = watch.Watch()


def update_job_status_in_db(job_name, status):
    try:
        connection = mysql.connector.connect(
            host='mariadb',
            database='exampledb',
            user='exampleuser',
            password='examplepass'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO job_status (job_name, status)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE status=%s
            """, (job_name, status, status))
            connection.commit()
    except Error as e:
        print("Error while connecting to MariaDB", e)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def watch_jobs():
    for event in w.stream(batch_v1.list_namespaced_job, namespace='default'):
        job = event['object']
        job_name = job.metadata.name
        if job.status.succeeded is not None:
            status = 'Complete'
        elif job.status.failed is not None:
            status = 'Failed'
        else:
            status = 'Running'

        print(f"Job {job_name} status: {status}")
        update_job_status_in_db(job_name, status)


def main():
    while True:
        try:
            watch_jobs()
        except Error as e:
            print("Error in processing loop", e)


if __name__ == "__main__":
    main()
