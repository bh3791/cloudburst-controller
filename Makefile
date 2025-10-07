DEPLOYMENT_ID=cloudburst-controller

IMAGE_NAME=bhdockr/$(DEPLOYMENT_ID)
VERSION=0.1.1
NAMED_VERSION=mini-raptor
GIT_SHA=$(shell git rev-parse --short HEAD)

K8S_IP=bruce-mint
STORAGE_IP=bruce@bruce-mint #bruce@bruce-m2.local

#AWS_ID=$(AWS_ID) # your AWS account ID here, if using AWS. Using an ENV variable
#AWS_REGION=$(AWS_REGION) # your preferred AWS region here, if using AWS. Using an ENV variable
#GAR_REPO_PREFIX=$(GAR_REPO_PREFIX) # e.g. us-west2-docker.pkg.dev. Using an ENV variable
#GAR_PROJECT_ID=$(GAR_PROJECT_ID) # your Google Cloud Project ID, if using. An ENV variable
#ECR_REPO_ID=$(DEPLOYMENT_ID)
#ECR_REPO_URL=$(AWS_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

# Build Docker images using Docker Compose
build:
	docker compose build --build-arg VERSION=$(VERSION) --build-arg GIT_SHA=$(GIT_SHA)

# Tag the image after building with Docker Compose
tag:
	docker tag $(IMAGE_NAME) $(IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME) $(IMAGE_NAME):$(NAMED_VERSION)
	docker tag $(IMAGE_NAME) $(IMAGE_NAME):$(GIT_SHA)

# Push Docker images using Docker Compose and manually for tags
push: build tag
	docker compose push
	docker push $(IMAGE_NAME):$(VERSION)
	docker push $(IMAGE_NAME):$(NAMED_VERSION)
	docker push $(IMAGE_NAME):$(GIT_SHA)

build2:
	docker compose build $(DEPLOYMENT_ID)

build-nocache:
	docker compose build --no-cache $(DEPLOYMENT_ID)

run: build
	docker compose run --rm --entrypoint bash $(DEPLOYMENT_ID)

test: build
	docker compose up --remove-orphans $(DEPLOYMENT_ID)

auth-ecr:
	kubectl delete secret regcred
	kubectl create secret docker-registry regcred \
  		--docker-server=$(AWS_ID).dkr.ecr.$(AWS_REGION).amazonaws.com \
  		--docker-username=AWS \
  		--docker-password=$$(aws ecr get-login-password)

push-ecr: build
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REPO_URL)
	docker tag $(DEPLOYMENT_ID):latest $(ECR_REPO_URL)/$(ECR_REPO_ID):latest
	docker push $(ECR_REPO_URL)/$(ECR_REPO_ID):latest

push-gar: build
	# gcloud auth configure-docker $(GAR_REPO_PREFIX)
	docker tag $(DEPLOYMENT_ID)-$(DEPLOYMENT_ID):latest $(GAR_REPO_PREFIX)/$(GAR_PROJECT_ID)/$(DEPLOYMENT_ID)/$(DEPLOYMENT_ID):latest
	docker push $(GAR_REPO_PREFIX)/$(GAR_PROJECT_ID)/$(DEPLOYMENT_ID)/$(DEPLOYMENT_ID)

init-mq:
	kubectl apply -f deployment/rabbitmq-controller.yaml

delete-mq:
	kubectl delete -f deployment/rabbitmq-controller.yaml

init-controller:
	kubectl apply -f deployment/app-deployment.yaml
	kubectl apply -f deployment/cloudburst-metrics-service.yaml

delete-controller:
	kubectl delete -f deployment/cloudburst-metrics-service.yaml
	kubectl delete -f deployment/app-deployment.yaml

init-prometheus:
	kubectl apply -f deployment/prometheus-configmap.yaml
	kubectl apply -f deployment/kube-state-metrics.yaml
	kubectl apply -f deployment/prometheus-deployment.yaml

delete-prometheus:
	kubectl delete -f deployment/prometheus-deployment.yaml
	kubectl delete -f deployment/kube-state-metrics.yaml
	kubectl delete -f deployment/prometheus-configmap.yaml

jump-pod:
	echo kubectl run jump-1 -it --rm --image=$(IMAGE_NAME) bash

apply: init-controller apply-policy

re-apply: delete-controller apply

# run cloudburst
post-msg:
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item 12346 -count 1

# run la-haz
post-msg4:
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00001 -mode post -image bhdockr/la-haz:latest -container_name la-haz
post-msg3:
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00001 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00002 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00003 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00004 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00005 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00006 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00007 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00008 -mode haz -image bhdockr/la-haz:latest -container_name la-haz
	python3 mq_pub.py -queue job1 -broker_url amqp://guest:guest@$(K8S_IP):31672 -storage-type network-rsync -storage-container $(STORAGE_IP) -work_item Site00009 -mode haz -image bhdockr/la-haz:latest -container_name la-haz

update-configmaps:
	# the following secrets are used by the cloudburst job template
	kubectl create secret generic ssh-key --from-file=id_ed25519=$(HOME)/.ssh/id_ed25519

	# these configmaps are used to reduce the number of docker rebuilds
	kubectl delete configmap task-config
	kubectl delete configmap job-template
	kubectl create configmap task-config --from-file=../ucerf3-hazard/tasks.json
	kubectl create configmap job-template --from-file=cloudburst-job-template.yaml

monitor-ctrl:
	kubectl logs -l app=cloudburst-controller --follow --max-log-requests 40

monitor-jobs:
	kubectl logs -l app=la-haz --follow --max-log-requests 40

k3s-init:
	# was: kind create cluster --config deployment/kind-ports.yaml
	# now: install k3s
	curl -sfL https://get.k3s.io | sudo sh -

k3s-delete:
	sudo /usr/local/bin/k3s-uninstall.sh

setup: init-prometheus init-mq init-controller apply-policy update-configmaps

apply-policy:
	# permissions required for using the kubernetes batch job service
	kubectl apply -f deployment/service-account.yaml

remove-policy:
	kubectl apply -f deployment/service-account.yaml

remove-all: delete-prometheus delete-controller delete-mq delete-db remove-policy

clear-jobs:
	kubectl delete job --field-selector=status.successful=1
	kubectl delete job --field-selector=status.successful=0
