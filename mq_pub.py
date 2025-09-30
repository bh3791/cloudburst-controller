import pika
import argparse
import os
import json


parser = argparse.ArgumentParser()
parser.add_argument(
    "-work_item",
    dest="work_item",
    help="The work item to process",
    required=True)
parser.add_argument(
    "-count",
    dest="count",
    type=int,
    help="The number of items to issue",
    default=1)
parser.add_argument(
    "-namespace",
    dest="namespace",
    help="The job namespace to run in",
    default="default")
parser.add_argument(
    "-container_name",
    dest="container_name",
    help="The container name to run",
    default="cloudburst")
parser.add_argument(
    "-image",
    dest="image",
    help="The container image to run",
    default="bhdockr/cloudburst:latest")
parser.add_argument(
    "-queue",
    dest="queue_name",
    required=True,
    help="The queue name, if not the QUEUE env var",
    default=os.getenv("QUEUE"))
parser.add_argument(
    "-storage-type",
    dest = "storage_type",
    required = True,
    help = "The storage container/host type",
    default = os.getenv("STORAGE_TYPE"))
parser.add_argument(
    "-storage-container",
    dest="storage_container",
    required=True,
    help="The storage container/host",
    default=os.getenv("STORAGE_CONTAINER"))
parser.add_argument(
    "-broker_url",
    dest="broker_url",
    required=True,
    help="The broker to pass in, if not check BROKER_URL env var",
    default=os.getenv("BROKER_URL"))


def main():
    connection = pika.BlockingConnection(pika.URLParameters(url=args.broker_url))
    channel = connection.channel()
    channel.queue_declare(queue=args.queue_name)

    for i in range(0, args.count):
        # the following items will be substituted into the cloudburst-job-template.yaml when received
        request = {  # put the identifier element first
            "WORK_ITEM": args.work_item,
            "JOB_NAMESPACE": args.namespace,
            "CONTAINER_NAME": args.container_name,
            "CONTAINER_IMAGE": args.image,
            "STORAGE_TYPE": args.storage_type,
            "STORAGE_CONTAINER": args.storage_container
        }
        request_str = json.dumps(request)

        channel.basic_publish(exchange='', routing_key=args.queue_name, body=request_str)
        print(f" sent {args.work_item} to: {args.broker_url}/{args.queue_name}")


if __name__ == "__main__":
    args = parser.parse_args()
    main()
