# got-milk-monarchs

[FloraPalooza](https://github.com/Imageomics/FloraPalooza-2026) project for detecting Monarch butterfly chewing damage on Milkweed leaves. More information and the conclusions from our project are viewable in [our project presentation](https://docs.google.com/presentation/d/1baP8iX4cfTwQOn99cfgYlntlKyjzO_aR5Sy6F0k9z_Q/edit?usp=sharing).

## Data Processing

We sourced iNaturalist images of milkweed (*Asclepias syriaca*) from [TreeOfLife-200M](https://huggingface.co/datasets/imageomics/TreeOfLife-200M). The selected images for labeling were first clustered (using provided [BioCLIP 2 embeddings](https://huggingface.co/datasets/imageomics/TreeOfLife-200M-embeddings)); the embedding space showed correlation to developmental stages of the plants, and clusters corresponding to senescing plants were removed to expedite labeling. More details about the data used are provided in the [data directory](data).

The `labeling/` directory contains a self-hosted leaf-damage labeling interface. Please see [`labeling/README.md`](labeling/README.md) for interface use instructions and more details.

<img width="3024" height="1700" alt="damage-indicator-app" src="https://github.com/user-attachments/assets/81d32e64-83ed-4678-9fee-25ad012a0a3b" />
