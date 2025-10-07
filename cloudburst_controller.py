import json
import threading
import time
import traceback

import pika
import yaml
from string import Template
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from prometheus_client import Counter, Gauge, Histogram, start_http_server
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
#parser.add_argument(
#    "-image_name",
#    dest="image_name",
#    help="The name of the image to start",
#    default=os.getenv("IMAGE_NAME"))
#parser.add_argument(
#    "-image_url",
#    dest="image_url",
#    help="The URL of the image to start",
#    default=os.getenv("IMAGE_URL"))
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
    "-no-k8s",
    dest="no_k8s",
    action="store_true",
    help="Disable the k8s functions")
parser.add_argument(
    "-debug",
    dest="debug",
    action="store_true",
    help="write out more debug info")


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


METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
QUEUE_METRICS_INTERVAL_SECONDS = int(os.getenv("QUEUE_METRICS_INTERVAL_SECONDS", "5"))

job_creation_counter = Counter(
    "cloudburst_jobs_created_total",
    "Total number of Kubernetes Jobs created",
    ["queue"])
job_creation_failures = Counter(
    "cloudburst_job_creation_failures_total",
    "Number of Kubernetes Job creation attempts that failed",
    ["queue"])
job_creation_latency = Histogram(
    "cloudburst_job_submission_duration_seconds",
    "Time spent submitting a Job to the Kubernetes API",
    ["queue"])
messages_consumed_counter = Counter(
    "cloudburst_messages_consumed_total",
    "Total number of RabbitMQ messages consumed and processed",
    ["queue"])
running_jobs_gauge = Gauge(
    "cloudburst_jobs_running",
    "Current number of Jobs in running or pending state",
    ["queue"])
queue_depth_gauge = Gauge(
    "cloudburst_queue_depth",
    "Current number of messages waiting in the RabbitMQ queue",
    ["queue"])
queue_consumers_gauge = Gauge(
    "cloudburst_queue_consumers",
    "Number of active RabbitMQ consumers for the queue",
    ["queue"])


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
            job_name = f"job-cb-{value1}-{int(time.time_ns()/1000)}".lower()
            my_vars["JOB_NAME"] = job_name
            if args.debug:
                print(f"naming job {job_name} based on {name1}")
            b_named = True
        elif name1 == "JOB_NAMESPACE":
            job_namespace = value1

    # name the job something if it was not already named
    if not b_named:
        for name1, value1 in message.items():
            job_name = f"job-cb-{value1}-{int(time.time_ns()/1000)}".lower()
            my_vars["JOB_NAME"] = job_name
            if args.debug:
                print(f"naming job {job_name} based on {name1}")
                break

    job_manifest = substitute_template(job_template, my_vars)
    if args.debug:
        print(f"DEBUG: job_manifest: {job_manifest}")

    try:
        with job_creation_latency.labels(queue=args.queue_name).time():
            batch_v1.create_namespaced_job(body=job_manifest, namespace=job_namespace)
        job_creation_counter.labels(queue=args.queue_name).inc()
        print(f"Job {job_name} created successfully in namespace {job_namespace}")
    except ApiException as e:
        job_creation_failures.labels(queue=args.queue_name).inc()
        print(f"Exception when creating job: {e}")
        traceback.print_exc()


# Retrieve the number of current running and pending jobs
def get_running_jobs():
    try:
        jobs = batch_v1.list_namespaced_job(namespace="default")
        running_jobs = [job for job in jobs.items if job.status.active or (job.status.conditions and any(
            condition.type == "PodScheduled" and condition.status == "True" for condition in job.status.conditions))]

        running_jobs_count = len(running_jobs)
        running_jobs_gauge.labels(queue=args.queue_name).set(running_jobs_count)
        return running_jobs_count
    except ApiException as e:
        print(f"Exception when listing jobs: {e}")
        traceback.print_exc()
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
        messages_consumed_counter.labels(queue=args.queue_name).inc()
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Failed to process message: {e}")
        traceback.print_exc()


# Function to start consuming messages from RabbitMQ
def start_consuming():
    mq_url = args.broker_url

    print(f"listening on: {mq_url} queue: {args.queue_name}")
    connection = pika.BlockingConnection(pika.URLParameters(mq_url))
    channel = connection.channel()
    channel.queue_declare(queue=args.queue_name)
    channel.basic_consume(queue=args.queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()


def queue_depth_monitor():
    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(args.broker_url))
            channel = connection.channel()
            channel.queue_declare(queue=args.queue_name)
            while True:
                queue_state = channel.queue_declare(queue=args.queue_name, passive=True)
                queue_depth_gauge.labels(queue=args.queue_name).set(queue_state.method.message_count)
                queue_consumers_gauge.labels(queue=args.queue_name).set(queue_state.method.consumer_count)
                time.sleep(QUEUE_METRICS_INTERVAL_SECONDS)
        except Exception as exc:
            if args.debug:
                print(f"Queue depth monitor encountered an error: {exc}")
            time.sleep(QUEUE_METRICS_INTERVAL_SECONDS)
        finally:
            if connection and connection.is_open:
                try:
                    connection.close()
                except Exception:
                    pass


# Main function to start multiple threads
def main():

    # this is for testing the functionality of the service up to the point of submitting the jobs
    if not args.no_k8s:
        start_http_server(METRICS_PORT)
        monitor_thread = threading.Thread(target=queue_depth_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

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
