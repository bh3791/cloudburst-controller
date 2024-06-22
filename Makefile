DEPLOYMENT_ID=cloudburst-controller

#AWS_ID=$(AWS_ID) # your AWS account ID here, if using AWS. Using an ENV variable
#AWS_REGION=$(AWS_REGION) # your preferred AWS region here, if using AWS. Using an ENV variable
#GAR_REPO_PREFIX=$(GAR_REPO_PREFIX) # e.g. us-west2-docker.pkg.dev. Using an ENV variable
#GAR_PROJECT_ID=$(GAR_PROJECT_ID) # your Google Cloud Project ID, if using. An ENV variable

ECR_REPO_ID=$(DEPLOYMENT_ID)
ECR_REPO_URL=$(AWS_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

build:
	docker compose build $(DEPLOYMENT_ID)

build-nocache:
	docker compose build --no-cache $(DEPLOYMENT_ID)

run: build
	docker compose run --rm --entrypoint bash $(DEPLOYMENT_ID)

test: build
	docker compose up --remove-orphans $(DEPLOYMENT_ID)

re-auth:
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
	kubectl apply -f deployment/rabbitmq-service.yaml

delete-mq:
	kubectl delete -f deployment/rabbitmq-service.yaml
	kubectl delete -f deployment/rabbitmq-controller.yaml

init-controller:
	kubectl apply -f deployment/app-deployment.yaml

delete-controller:
	kubectl delete -f deployment/app-deployment.yaml

jump-pod:
	echo kubectl run jump-1 -it --rm --image=us-west2-docker.pkg.dev/$(GCR_PROJECT_ID)/$(DEPLOYMENT_ID)/$(DEPLOYMENT_ID) bash

apply: push-gar init-controller apply-policy

re-apply: delete-controller apply

post-msg:
	python mq_pub.py -queue job1 -broker_url amqp://guest:guest@localhost:31672 -work_item 23234

monitor-ctrl:
	kubectl logs -l app=cloudburst-controller --follow

monitor-cb:
	kubectl logs -l app=cloudburst --follow

setup: init-mq push-gar init-controller apply-policy

apply-policy:
	# permissions required for using the kubernetes batch job service
	kubectl apply -f deployment/cluster-role.yaml
	kubectl apply -f deployment/service-account.yaml
	kubectl apply -f deployment/cluster-role-binding.yaml

remove-policy:
	kubectl apply -f deployment/cluster-role-binding.yaml
	kubectl apply -f deployment/cluster-role.yaml
	kubectl apply -f deployment/service-account.yaml

remove-all: delete-controller delete-mq remove-policy

