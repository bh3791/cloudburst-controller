# Cloudburst Controller for Kubernetes

The `cloudburst controller` is a container app which runs in kubernetes. The controller has a simple job, it listens to a rabbitmq queue and creates cloudburst jobs. A client tool (mq_pub.py) is provided to send requests to the rabbitmq channel.

RabbitMQ is exposed outside the cluster in the rabbitmq-service.yaml for ease of initial implementation and testing with the help of the mq_pub script.

The Makefile is used as a convenient way to build and deploy the container in a publicly accessible repo. It is used to deploy the components into the kubernetes cluster. To use the makefile, you must define some environment variables. Check the makefile to see which are needed. Use the command `make setup` to set up the message queue and controller.


The `app-deployment.yaml` script must be configured when implementing the service.
