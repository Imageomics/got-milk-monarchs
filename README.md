# got-milk-monarchs

FloraPalooza project for detecting Monarch butterfly chewing damage on Milkweed leaves.

## Data Processing

The `labeling/` directory contains a self-hosted leaf-damage labeling interface. Please see [`labeling/README.md`](labeling/README.md) for interface use instructions and more details.

We sourced iNaturalist images of milkweed (*Asclepias syriaca*) from [TreeOfLife-200M](https://huggingface.co/datasets/imageomics/TreeOfLife-200M). The selected images for labeling were first clustered (using provided BioCLIP 2 embeddings); the embedding space showed correlation to developmental stages of the plants, and clusters corresponding to senescing plants were removed to expedite labeling.
