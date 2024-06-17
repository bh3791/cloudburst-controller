Cloudburst Controller for Kubernetes

This server is a container app which runs the controller script, which is implemented in python. This script listens to a rabbitmq channel and creates cloudburst jobs in a kubernetes cluster. A client-side tool (mq_pub.py) is provided to send requests to the rabbitmq channel.

RabbitMQ is exposed outside the cluster in the rabbitmq-service.yaml for ease of initial implementation.

The Makefile is used as a convenient way to build and deploy the container in a publicly accessible repo. It is used to deploy the components into the kubernetes cluster.