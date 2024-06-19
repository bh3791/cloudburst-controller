import json
import threading
import time
import pika
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument(
    "-queue",
    dest="queue_name",
    help="The queue name, if not the QUEUE env var",
    default=os.getenv("QUEUE"))
parser.add_argument(
    "-broker_url",
    dest="broker_url",
    help="The broker to pass in, if not check BROKER_URL env var",
    default=os.getenv("BROKER_URL"))
parser.add_argument(
    "-container_name",
    dest="container_name",
    help="The name of the container to start",
    default=os.getenv("CONTAINER_NAME"))
parser.add_argument(
    "-container_url",
    dest="container_url",
    help="The URL of the container to start",
    default=os.getenv("CONTAINER_URL"))
parser.add_argument(
    "-num_threads",
    dest="num_threads",
    type=int,
    help="The number of threads to run",
    default=1)
parser.add_argument(
    "-max_concurrent_jobs",
    dest="max_concurrent_jobs",
    type=int,
    help="The max number of jobs to run concurrently",
    default=os.getenv("MAX_CONCURRENT_JOBS"))
parser.add_argument(
    "-test",
    dest="is_test",
    action="store_true",
    help="The broker to pass in, if not check BROKER_URL env var")
parser.add_argument(
    "-debug",
    dest="debug",
    action="store_true",
    help="The broker to pass in, if not check BROKER_URL env var")

try:
    # attempt to load in-cluster config, or else it's a docker setup
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

batch_v1 = client.BatchV1Api()


# Function to create a Kubernetes job
def create_kubernetes_job(message):

    # defaults for cpu and memory resources requested for each job
    cpu_request = "250m"
    memory_request = "64Mi"
    cpu_limit = "500m"
    memory_limit = "128Mi"

    # load up the environment variables
    my_env = []
    b_named = False
    job_name = "x"
    for name1, value1 in message.items():
        if not b_named:
            # use the first item found to identify the job name
            # make it unique with a timestamp
            job_name = f"job-cb-{value1}-{int(time.time_ns()/1000)}"
            if args.debug:
                print(f"creating {job_name}")
            b_named = True

        my_env.append(client.V1EnvVar(name=name1.upper(), value=value1))

    # Define the job
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=args.container_name,
                            image=args.container_url,
                            env=my_env,
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": cpu_request, "memory": memory_request},
                                limits={"cpu": cpu_limit, "memory": memory_limit}
                            )                        
                        )
                    ],
                    restart_policy="Never"
                )
            ),
            backoff_limit=4
        )
    )

    try:
        batch_v1.create_namespaced_job(body=job, namespace="default")
        print(f"Job {job_name} created successfully")
    except ApiException as e:
        print(f"Exception when creating job: {e}")


# Retrieve the number of current running and pending jobs
def get_running_jobs():
    try:
        jobs = batch_v1.list_namespaced_job(namespace="default")
        running_jobs = [job for job in jobs.items if job.status.active or (job.status.conditions and any(
            condition.type == "PodScheduled" and condition.status == "True" for condition in job.status.conditions))]

        return len(running_jobs)
    except ApiException as e:
        print(f"Exception when listing jobs: {e}")
        return []


# Function to process RabbitMQ messages
def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        if args.debug:
            print(f"received message: {message}")

        # throttle the number of currently running jobs, if max_concurrent_jobs is not None
        if args.max_concurrent_jobs is not None and args.max_concurrent_jobs > 0:
            while get_running_jobs() >= args.max_concurrent_jobs:
                if args.debug:
                    print(f"Maximum concurrent jobs ({args.max_concurrent_jobs}) running, waiting...")
                time.sleep(5)  # Wait before checking again

        create_kubernetes_job(message)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Failed to process message: {e}")


# Function to start consuming messages from RabbitMQ
def start_consuming():
    mq_url = args.broker_url

    print(f"listening on: {mq_url} queue: {args.queue_name}")
    connection = pika.BlockingConnection(pika.URLParameters(mq_url))
    channel = connection.channel()
    channel.queue_declare(queue=args.queue_name)
    channel.basic_consume(queue=args.queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()


# Main function to start multiple threads
def main():
    threads = []

    for _ in range(args.num_threads):
        thread = threading.Thread(target=start_consuming)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    args = parser.parse_args()
    main()
