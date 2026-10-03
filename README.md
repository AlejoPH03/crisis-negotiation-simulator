# Negotiation Simulation Project

This project simulates and evaluates multi-agent negotiations in a hostage negotiation scenario using Ollama's Gemma 3 model.

## Setup

1. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install required packages:
```bash
pip install ollama transformers sentence-transformers pandas matplotlib jupyter
```

3. Ensure Ollama is installed and running on your system with the Gemma 3 model:
```bash
ollama pull gemma3:1b
```

## Project Structure

```
negotiation_project/
├── data/                 # Raw negotiation transcripts
├── models/              # Fine-tuned checkpoints
├── src/                 # Source code
│   ├── simulate.py      # Main negotiation simulation loop
│   ├── prompts.py       # Persona and scenario prompt definitions
│   ├── metrics.py       # Functions to compute success rate, perplexity, efficiency
│   └── utils.py         # Shared helper functions
└── notebooks/           # Jupyter notebooks for visualization
```

## Running Experiments

To run the negotiation experiments:

```bash
cd src
python simulate.py
```

This will:
1. Run all experimental conditions (8 combinations of FBI strategies, criminal profiles, and who starts)
2. Save results to `data/negotiation_results.csv`

## Analyzing Results

To analyze and visualize the results:

1. Start Jupyter:
```bash
jupyter notebook
```

2. Open `notebooks/analyze_results.ipynb`

The notebook provides:
- Success rate analysis
- Efficiency metrics (rounds and time)
- Perplexity analysis
- Summary statistics

## Experimental Conditions

The simulation tests 8 different conditions:
- FBI strategies: empathy vs authority
- Criminal profiles: unstable vs calculated
- Starter: FBI vs criminal

Each condition is run multiple times to gather statistical significance.

## Metrics

The simulation tracks:
- Success rate (hostage release or surrender)
- Number of rounds to resolution
- Wall clock time
- Perplexity of the conversation

## Contributing

Feel free to submit issues and enhancement requests! 