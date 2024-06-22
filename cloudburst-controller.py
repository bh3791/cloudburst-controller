import json
import threading
import time
import pika
import yaml
from string import Template
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
    help="The max number of jobs to run concurrently. This is not recommended, instead k8s can use memory and cpu constraints to manage load",
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


def load_template(template_file):
    with open(template_file, 'r') as file:
        template = Template(file.read())
    return template


# attempt to load in-cluster config, or else it's a docker setup
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

# init the batch API
batch_v1 = client.BatchV1Api()

# load the YAML job template
job_template_file = 'cloudburst-job-template.yaml'
job_template = load_template(job_template_file)


def substitute_template(template, variables):
    substituted_content = template.substitute(variables)
    return yaml.safe_load(substituted_content)


def create_kubernetes_job(message):
    # load up the substitution variables
    my_vars = {}
    b_named = False
    job_name = "x"
    job_namespace = "default"

    # create the substitution variables based on the request message.
    # extract the job name and namespace when provided
    for name1, value1 in message.items():
        my_vars[name1.upper()] = value1

        if name1 == "WORK_ITEM":
            # try to find work_item to identify the job name, make it unique with a timestamp
            job_name = f"job-cb-{value1}-{int(time.time_ns()/1000)}"
            my_vars["JOB_NAME"] = job_name
            if args.debug:
                print(f"naming job {job_name} based on {name1}")
            b_named = True
        elif name1 == "JOB_NAMESPACE":
            job_namespace = value1

    # name the job something if it was not already named
    if not b_named:
        for name1, value1 in message.items():
            job_name = f"job-cb-{value1}-{int(time.time_ns()/1000)}"
            my_vars["JOB_NAME"] = job_name
            if args.debug:
                print(f"naming job {job_name} based on {name1}")
                break

    job_manifest = substitute_template(job_template, my_vars)

    try:
        batch_v1.create_namespaced_job(body=job_manifest, namespace=job_namespace)
        print(f"Job {job_name} created successfully in namespace {job_namespace}")
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
