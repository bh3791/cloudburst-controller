import time
from kubernetes import client, config
import mysql.connector
from mysql.connector import Error


# attempt to load in-cluster config, or else it's a docker setup
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
# load batch API
batch_v1 = client.BatchV1Api()


def get_job_status():
    # Load Kubernetes configuration
    jobs = batch_v1.list_namespaced_job(namespace='default')

    job_statuses = []
    for job in jobs.items:
        job_name = job.metadata.name
        if job.status.succeeded is not None:
            status = 'Complete'
        elif job.status.active is not None:
            status = 'Running'
        elif job.status.failed is not None:
            status = 'Failed'
        else:
            status = 'Unknown'
        job_statuses.append((job_name, status))
    return job_statuses

def update_mariadb(job_statuses):
    try:
        connection = mysql.connector.connect(
            host='mariadb',
            database='exampledb',
            user='exampleuser',
            password='examplepass'
        )

        if connection.is_connected():
            cursor = connection.cursor()
            for job_name, status in job_statuses:
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


def main():
    while True:
        try:
            job_statuses = get_job_status()
            update_mariadb(job_statuses)
            time.sleep(30)
        except Error as e:
            print("Error in processing loop", e)


if __name__ == "__main__":
    main()
