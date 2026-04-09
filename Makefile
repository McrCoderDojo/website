export BEEMO_CONFIG=config.yml

.PHONY: build logs analytics serve serve-analytics

build:
	BEEMO_CONFIG=$(BEEMO_CONFIG) beemo build

logs:
	BEEMO_CONFIG=$(BEEMO_CONFIG) beemo logs

analytics:
	BEEMO_CONFIG=$(BEEMO_CONFIG) beemo analytics

serve:
	python -m http.server -d www 8000

serve-analytics:
	python -m http.server -d analytics 8000