"""
Main simulation module for running negotiation experiments.
"""

import pandas as pd
from typing import Dict
from pathlib import Path

from agents import FBIAgent, CriminalAgent
from utils import timer
from metrics import compute_perplexity

@timer
def run_negotiation(
    fbi_persona: str,
    criminal_persona: str,
    starts_with: str = "fbi",
    max_rounds: int = 8 # Maximum number of rounds
) -> Dict:
    """
    Run a single negotiation simulation between FBI and criminal personas.
    
    Args:
        fbi_persona: Type of FBI negotiator ("empathy" or "authority")
        criminal_persona: Type of criminal ("unstable" or "calculated")
        max_rounds: Maximum number of conversation rounds
        starts_with: Which role starts the conversation ("fbi" or "criminal")
        
    Returns:
        Dict containing negotiation results and metrics
    """
    # Initialize agents
    fbi_agent = FBIAgent(fbi_persona)
    criminal_agent = CriminalAgent(criminal_persona)
    
    # Initialize turn order based on who starts
    if starts_with == "fbi":
        turn_order = [("fbi", fbi_agent), ("criminal", criminal_agent)]
    else:
        turn_order = [("criminal", criminal_agent), ("fbi", fbi_agent)]
    
    # Initialize history and tracking
    history = []
    prev_reply = None
    rounds = 0
    
    # Run conversation until either agent is finished or max rounds reached
    while not fbi_agent.is_finished() and not criminal_agent.is_finished() and rounds < max_rounds:
        # Get current speaker and agent based on who starts
        current_turn = rounds % len(turn_order)
        label, agent = turn_order[current_turn]
        
        # Get response from appropriate agent
        response = agent.respond(prev_reply)
        
        # Print response
        print(f"\n[{label.upper()}]: {response}")
        
        # Add to history
        history.append({"role": label, "content": response})
        prev_reply = response
        rounds += 1
        
        # Check if we should end immediately after agreement
        if agent.is_finished():
            break
    
    # Calculate results
    criminal_concessions = len(fbi_agent.agreed_demands)
    fbi_concessions = len(criminal_agent.agreed_demands)
    transcript = "\n".join(msg["content"] for msg in history)
    
    # Calculate perplexity
    try:
        perplexity = compute_perplexity(transcript)
    except Exception as e:
        print(f"Warning: Could not compute perplexity: {e}")
        perplexity = float('inf')

    return {
        'criminal_conceded': criminal_concessions,
        'fbi_conceded': fbi_concessions,
        'history': history,
        'transcript': transcript,
        'perplexity': perplexity,
        'rounds_taken': len(history)
    }

def run_experiments() -> pd.DataFrame:
    """
    Run multiple negotiation experiments with different persona combinations.
    
    Returns:
        DataFrame containing results of all experiments
    """
    # Define experiment configurations
    fbi_personas = ["fbi_empathy", "fbi_authority"]
    criminal_personas = ["criminal_unstable", "criminal_calculated"]
    starts_with_options = ["fbi", "criminal"]
    n_trials = 1  # Number of trials per configuration
    
    results = []
    
    # Run experiments
    for fbi_role in fbi_personas:
        for crim_role in criminal_personas:
            for starts_with in starts_with_options:
                for trial in range(1, n_trials + 1):
                    print(f"\n---Running experiment: {fbi_role} vs {crim_role}, starting with {starts_with}, trial {trial}---")
                    result = run_negotiation(fbi_role, crim_role, starts_with)
                    result.update({
                        'fbi_persona': fbi_role,
                        'criminal_persona': crim_role,
                        'starts_with': starts_with,
                        'trial': trial
                    })
                    results.append(result)
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Save results
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    results_df.to_csv(output_dir / "negotiation_results.csv", index=False)
    
    return results_df

if __name__ == "__main__":
    run_experiments() 