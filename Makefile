DEPLOYMENT_ID=cloudburst-controller

IMAGE_NAME=bhdockr/$(DEPLOYMENT_ID)
VERSION=0.1.1
NAMED_VERSION=mini-raptor
GIT_SHA=$(shell git rev-parse --short HEAD)

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

init-db:
	kubectl apply -f deployment/mariadb-deployment.yaml

delete-db:
	kubectl apply -f deployment/mariadb-deployment.yaml

init-controller:
	kubectl apply -f deployment/app-deployment.yaml

delete-controller:
	kubectl delete -f deployment/app-deployment.yaml

jump-pod:
	echo kubectl run jump-1 -it --rm --image=us-west2-docker.pkg.dev/$(GCR_PROJECT_ID)/$(DEPLOYMENT_ID)/$(DEPLOYMENT_ID) bash

apply: init-controller apply-policy

re-apply: delete-controller apply

post-msg:
	python mq_pub.py -queue job1 -broker_url amqp://guest:guest@localhost:31672 -work_item 12345 -count 1

sql-conn:
	mysql -h 127.0.0.1 -P 30306 -uroot -prootpassword exampledb

sql-init:
	mysql -h 127.0.0.1 -P 30306 -uroot -prootpassword exampledb < database/job_status.sql

monitor-ctrl:
	kubectl logs -l app=cloudburst-controller --follow

monitor-cb:
	kubectl logs -l app=cloudburst --follow

setup: init-mq init-db init-controller apply-policy sql-init

apply-policy:
	# permissions required for using the kubernetes batch job service
	kubectl apply -f deployment/service-account.yaml

remove-policy:
	kubectl apply -f deployment/service-account.yaml

remove-all: delete-controller delete-mq delete-db remove-policy

clear-jobs:
	kubectl delete job --field-selector=status.successful=1
