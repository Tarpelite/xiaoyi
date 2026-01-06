.PHONY: download-gift-eval-data upload-data-to-s3

download-gift-eval-data:
	@huggingface-cli download Salesforce/GiftEval --repo-type=dataset --local-dir=./data/gift-eval

upload-data-to-s3: download-gift-eval-data
	@aws s3 sync ./data/gift-eval s3://timecopilot-gift-eval/data/gift-eval
