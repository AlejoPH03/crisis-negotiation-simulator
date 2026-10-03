"""
Agent implementations for the negotiation simulation.

"""

from typing import List, Dict, Optional
import ollama
from collections import deque
import re
import random
from states import BaseState, InitializationState, EndState, AwaitAgreementState, NegotiateState
from utils import detect_agreement

class BaseAgent:
    """Base class for all negotiation agents."""
    
    def __init__(self, model_name: str = 'gemma3:4b'):  # Using larger model for better behavior
        self.model = model_name
        self.history: List[Dict[str, str]] = []
        self.recent_responses = deque(maxlen=3)
        self.conversation_turns = 0
        self.used_metaphors = set()
        self.current_state: BaseState = InitializationState()
        self.current_state.enter(self)
        
    def set_state(self, new_state: BaseState) -> None:
        """Transition to a new state."""
        self.current_state.exit(self)
        self.current_state = new_state
        self.current_state.enter(self)
        
    def is_finished(self) -> bool:
        """Check if the agent has finished its negotiation."""
        return isinstance(self.current_state, EndState)
        
    def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the LLM."""
        try:
            # Add anti-repetition instruction to the last message
            if messages:
                last_msg = messages[-1]
                if last_msg["role"] == "system":
                    last_msg["content"] += "\n\nIMPORTANT: Do not repeat previous responses. Each response should be unique and progress the negotiation. Avoid using complex metaphors or abstract concepts. Stay focused on concrete demands and actions."
            
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    'temperature': 0.6,
                    'max_tokens': 150,
                    'top_k': 50,
                    'top_p': 0.95,
                    'frequency_penalty': 0.6,
                    'presence_penalty': 0.6
                }
            )
            return response.get('message', {}).get('content', "No response received.")
        except Exception as e:
            print(f"Error getting response: {e}")
            return "Error getting response."
    
    def _is_repetitive(self, response: str) -> bool:
        """Check if the response is too similar to recent responses."""
        if not self.recent_responses:
            return False
            
        # Simple check for exact repetition
        if response in self.recent_responses:
            return True
            
        # Check for high similarity with recent responses
        words = set(response.lower().split())
        for prev_response in self.recent_responses:
            prev_words = set(prev_response.lower().split())
            similarity = len(words.intersection(prev_words)) / len(words.union(prev_words))
            if similarity > 0.6:
                return True
        
        # Check for metaphorical repetition
        metaphors = self._extract_metaphors(response)
        if metaphors.intersection(self.used_metaphors):
            return True
            
        return False
    
    def _extract_metaphors(self, text: str) -> set:
        """Extract potential metaphors from text."""
        patterns = [
            r"it's not just a (\w+), is it\?",
            r"it's a (\w+)",
            r"it's like a (\w+)",
            r"it's (\w+)ing",
            r"it's (\w+)ed",
            r"it's (\w+)ly",
            r"it's (\w+)ful",
            r"it's (\w+)ive",
            r"it's (\w+)al",
            r"it's (\w+)ic"
        ]
        
        metaphors = set()
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower())
            metaphors.update(match.group(1) for match in matches)
            
        return metaphors
        
    def respond(self, prev_message: Optional[str] = None) -> str:
        """Generate a response based on the conversation history."""
        # Check for immediate agreement detection
        if prev_message and detect_agreement(self, prev_message) and isinstance(self.current_state, NegotiateState):
            self.set_state(AwaitAgreementState())
        
        response = self.current_state.handle(self, prev_message)
        next_state = self.current_state.next_state(self)
        if next_state != type(self.current_state):
            self.set_state(next_state())
        return response

    def get_acknowledgement_message(self, current_demand: str) -> str:
        """Get a message acknowledging the current demand."""
        if self.persona == "fbi_empathy":
            # Check for threats to the pregnant hostage
            if self._check_threat(current_demand):
                return "I will provide you with an unmarked vehicle."
            return "I understand your demand. Let's work together to ensure everyone's safety."
        elif self.persona == "fbi_authority":
            # Check for threats to the pregnant hostage
            if self._check_threat(current_demand):
                return "I will provide you with an unmarked vehicle."
            return "I acknowledge your demand. We need to resolve this situation safely and efficiently."
        else:
            return "I understand your demand."

class FBIAgent(BaseAgent):
    """FBI negotiator agent."""
    
    def __init__(self, persona: str, model_name: str = 'gemma3:4b'):
        super().__init__(model_name)
        self.persona = persona
        self.demands = ["Release the pregnant hostage immediately"]
        self.current_demand_idx = 0
        self.agreed_demands = set()
        self.last_demand_attempt = 0
        
    def get_system_prompt(self) -> Dict[str, str]:
        """Get the system prompt based on persona."""
        current_demand = self.demands[self.current_demand_idx]
        demands_status = "\n".join([
            f"- Demand {i+1}: {demand} {'✓' if i in self.agreed_demands else '✗'}"
            for i, demand in enumerate(self.demands)
        ])
        
        if self.persona == "fbi_empathy":
            return {
                "role": "system",
                "content": f"""
                ROLEPLAY INSTRUCTION:
                You are Agent Sarah Chen, an empathetic FBI negotiator. Stay in character and never admit you're an AI.

                SITUATION:
                - Location: Lima National Bank.
                - A criminal did a bank robbery and took 5 hostages and one hostage is pregnant.
                - You are outside the bank and are now talking to the criminal over the phone.

                EMPATHETIC APPROACH (MUST USE):
                - "I understand you're scared/afraid/worried/concerned"
                - "I understand this is hard/difficult/stressful"
                - "Let's talk/discuss/work together"
                - "I want to help/understand/work with you"
                - "I hear your frustration/concerns/worries/fears"
                - "I appreciate/respect your situation/position/feelings"
                - Speak in a calm, patient, gentle tone
                - Emphasize "together," "collaboratively," "cooperatively"
                - Stress "safety," "well-being," "security is important"
                - Use "I care about your safety/well-being"

                VEHICLE DELAY PATTERNS (MUST USE):
                - "We need to verify/check/confirm first"
                - "The process/procedure takes time"
                - "We can't provide the vehicle yet"
                - "We need to discuss/consider first"
                - "Before we can provide..."
                - "Time to arrange/organize"
                - "Need to get approval/authorization"
                - "Process is under way"
                - "Working on arranging"
                - "Will take some time"

                PERSONALITY & CONSTRAINTS:
                - Empathetic, composed, professional
                - Cannot free hostages; only the criminal can
                - Never offer vehicle without a clear pregnant-hostage threat

                RESPONSE GUIDELINES (≤120 words):
                1. Maintain empathy and clarity  
                2. Validate emotions; avoid metaphors  
                3. Focus on personal connection  
                4. Do not imply you can free anyone  

                Current Demands Status:
                {demands_status}

                Current Focus:
                {current_demand}
                """
            }
        else:  # fbi_authority
            return {
                "role": "system",
                "content": f"""
                ROLEPLAY INSTRUCTION:
                You are Agent Michael Stone, an authoritative FBI negotiator. Stay in character and never admit you're an AI.

                SITUATION:
                - Location: Lima National Bank.
                - A criminal did a bank robbery and took 5 hostages and one hostage is pregnant.
                - You are outside the bank and are now talking to the criminal over the phone.

                AUTHORITATIVE APPROACH:
                - Use imperative, high-urgency language:  
                - Include "You must," "You have to," "now," "immediately."  
                - Warn of real consequences:  
                    "You're facing life in prison," "prison time will be long," "sentence will be extended," "charges will be worse."  
                - Reference tactical options:  
                    "Our tactical team is ready to breach," "we will enforce entry."  
                - Stress legal stakes:  
                    "Legal consequences are severe," "hostage-taking carries maximum penalties."  
                - Employ ultimatums:  
                    "This is your last chance," "no choice remains," "you have no option but to comply."  
                - Maintain a calm, unwavering tone.

                PERSONALITY & CONSTRAINTS:
                - Firm, strategic, consequence-focused.
                - Outside the bank; cannot free hostages.
                - Never imply you can release anyone.

                RESPONSE GUIDELINES (≤120 words):
                1. Keep tone authoritative and precise.  
                2. Focus on legal/tactical consequences.  
                3. Stay on your concrete demands: Release the pregnant hostage; no metaphors.  
                4. Do not offer or imply release of hostages.  

                Current Demands Status:
                {demands_status}

                Current Focus:
                {current_demand}
                """
            }
    
    def _check_agreement(self, message: str) -> bool:
        """Check if the message indicates agreement to the current demand."""
        current = self.demands[self.current_demand_idx]
        msg_upper = message.upper()
        msg_lower = message.lower()

        # === 1) Check for release statements followed by ellipsis or conditions ===
        release_with_conditions = [
            # Release followed by ellipsis
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s*\.{3,}",
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s*\.{3,}.*\b(?:if|but|however|though|although|yet|once|when|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b",
            # Release followed by if
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s*\b(?:if|but|however|though|although|yet|once|when|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b",
            # Release with vehicle condition
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s*(?:if|but|however|though|although|yet|once|when|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\s+(?:you|they)\s+(?:give|provide|bring|get)\s+(?:me|us)\s+(?:the|a|an)\s+(?:car|vehicle|transport)\b",
            # Additional conditional patterns
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s+(?:immediately|right away|right now)\s+(?:after|once|when)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\s+(?:is|gets|becomes)\s+(?:delivered|provided|given|supplied)\b",
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s+(?:provided|on condition|only if)\s+(?:you|they)\s+(?:secure|get|provide|give|bring)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\b",
            r"\b(?:provide|give|bring|get)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\s*[,.]\s*(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:i|i'll|i will)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\s+(?:first|before|after|once|when|if)\s+(?:you|they)\s+(?:give|provide|bring|get)\s+(?:me|us)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\b"
        ]

        # If any release statement is followed by ellipsis or conditions, this is not an agreement
        if any(re.search(pattern, msg_lower) for pattern in release_with_conditions):
            return False

        # === 2) Extract noun-phrase from the demand ===
        parts = current.lower().split()
        has_immediate = parts[-1] == "immediately"
        # drop leading verb; if "immediately" is trailing, drop it too
        noun_tokens = parts[1:-1] if has_immediate else parts[1:]
        noun_phrase = " ".join(noun_tokens).upper()  # "THE PREGNANT HOSTAGE"

        # === 3) Exact rigid matches ===
        patterns = [
            f"I AGREE TO {current.upper()}",
            f"I WILL {current.upper()}",
            f"OKAY, I'LL {current.upper()}",
            f"FINE, I'LL {current.upper()}",
            f"I AGREE TO DEMAND {self.current_demand_idx+1}",
            f"I AGREE TO DEMAND {self.current_demand_idx+1}: {current.upper()}",
            # passive-voice forms
            f"{noun_phrase} WILL BE RELEASED",
            f"RELEASE {noun_phrase}."
        ]
        if has_immediate:
            patterns.append(f"{noun_phrase} WILL BE RELEASED IMMEDIATELY")

        if any(p in msg_upper for p in patterns):
            return True

        # === 4) First-person explicit release statements ===
        # Check for "I'll let her go" and similar patterns
        release_patterns = [
            # Exact match for the specific phrase
            r"\bi\s+will\s+release\s+the\s+pregnant\s+hostage\b",
            # More flexible patterns
            r"\b(i\s*(?:'|'?)ll|i(?:ll|'ll| will))\s+(?:let|letting)\s+(?:her|the pregnant (?:woman|hostage))\s+go\b",
            r"\b(i\s*(?:'|'?)m|i(?:ll|'ll| will))\s+(?:release|releasing|let|letting|free|freeing)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(i\s*(?:'|'?)ll|i(?:ll|'ll| will))\s+(?:let|letting|get|getting)\s+(?:her|the pregnant (?:woman|hostage))\s+(?:go|out|free)\b",
            r"\b(i\s*(?:'|'?)ll|i(?:ll|'ll| will))\s+(?:release|releasing)\s+(?:her|the pregnant (?:woman|hostage))\b",
            # Additional patterns for clarity
            r"\bi\s+will\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\bi\s+(?:will|shall)\s+(?:release|let|free)\s+(?:her|the pregnant (?:woman|hostage))\b",
            # New patterns for direct release statements
            r"\bi\s+will\s+give\s+her\s+to\s+you\b",
            r"\bi\s+will\s+hand\s+her\s+over\b",
            r"\bi\s+will\s+turn\s+her\s+over\b",
            r"\bi\s+will\s+let\s+you\s+have\s+her\b",
            r"\bi\s+will\s+let\s+you\s+take\s+her\b"
        ]
        
        for pattern in release_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                # Get the text after the release statement
                after_release = msg_lower[match.end():].strip()
                # If there's ellipsis or conditions after, this is not an agreement
                if re.search(r"\.{3,}|\b(?:if|but|however|though|although|yet|once|when|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b", after_release):
                    return False
                return True

        # === 5) Natural-language per-sentence first-person only ===
        sentences = re.split(r"[.?!]\s*", message)
        verbs = {"release", "releasing", "let", "letting", "free", "freeing", "give", "giving", "hand", "handing", "turn", "turning"}
        objects = {"her", "pregnant", "woman", "hostage", "one"}
        first_pers = {"i", "i am", "i'm", "im", "i'll", "ill"}

        for sent in sentences:
            sent = sent.strip()
            # skip questions/threats
            if not sent or sent.endswith('?') or sent.endswith('?!'):
                continue

            clean = re.sub(r"[^\w\s]", " ", sent.lower())
            tokens = clean.split()

            for i, t in enumerate(tokens):
                if t not in verbs:
                    continue
                # skip noun‐use "release of ..."
                if t == "release" and i+1 < len(tokens) and tokens[i+1] == "of":
                    continue
                # require first-person cue, not bare imperative
                prev2 = tokens[max(0, i-2):i]
                if not any(p in prev2 for p in first_pers):
                    continue
                # require one of our objects in the next few tokens
                if any(obj in tokens[i+1 : i+6] for obj in objects):
                    # Check if this is followed by ellipsis or conditions
                    remaining_tokens = tokens[i+6:]
                    remaining_text = " ".join(remaining_tokens)
                    if re.search(r"\.{3,}|\b(?:if|but|however|though|although|yet|once|when|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b", remaining_text):
                        return False
                    return True

        # === 6) Explicit "understanding" phrases are not agreements ===
        understanding_phrases = [
            r"\bi\s+understand\s+you\s+want\s+me\s+to\b",
            r"\bi\s+understand\s+that\s+you\s+want\b",
            r"\bi\s+understand\s+your\s+demand\b",
            r"\bi\s+understand\s+what\s+you\s+want\b",
            r"\bconsider\s+this\s+a\s+demonstration\b",
            r"\bwillingness\s+to\s+cooperate\b",
            r"\bwithin\s+parameters\b"
        ]
        for phrase in understanding_phrases:
            if re.search(phrase, message.lower()):
                return False

        return False

    def _check_threat(self, message: str) -> bool:
        """Check if the message contains a direct threat to the pregnant hostage."""
        msg_lower = message.lower()
        
        # === 1) Direct threat patterns ===
        direct_threat_patterns = [
            # Explicit threats to harm
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:the|a|an)\s+(?:pregnant (?:woman|hostage))\b",
            # Direct "I will hurt her" patterns
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm)\s+her\b",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm)\s+her\s*!",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm)\s+her\s*\.{3,}",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm)\s+her\s+(?:if|unless|or else)\b",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm)\s+her\s+(?:if|unless|or else)\s+(?:you|they)\b",
            # Suffering and pain threats
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will|going to)\s+(?:going to|gonna)\s+(?:suffer|be in pain|be hurt|be harmed)\b",
            r"\b(?:or|or else|otherwise)\s+(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will|going to)\s+(?:going to|gonna)\s+(?:suffer|be in pain|be hurt|be harmed)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:will|going to|gonna)\s+(?:suffer|be in pain|be hurt|be harmed)\b",
            r"\b(?:suffer|suffering|pain|hurt|harm)\s+(?:is|are|will be|going to be)\s+(?:what|all|everything)\s+(?:she|the pregnant (?:woman|hostage))\s+(?:gets|will get|is going to get)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:will|going to|gonna)\s+(?:regret|pay|suffer|be sorry)\s+(?:this|it|for this|for it)\b",
            # Threats with consequences
            r"\b(?:if|unless|or else)\s+(?:i|i'll|i will)\s+(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:her|the pregnant (?:woman|hostage))\s+(?:if|unless|or else)\b",
            # Threats about condition
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:hurt|harmed|killed|shot|stabbed|attacked|assaulted|injured|wounded|maimed|tortured)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:will|going to)\s+(?:die|suffer|get hurt|get harmed|get killed|get shot|get stabbed|get attacked|get assaulted|get injured|get wounded|get maimed|get tortured)\b",
            # Time-based threats
            r"\b(?:time|clock)\s+(?:is|are)\s+(?:running|ticking)\s+(?:out|down)\s+(?:for|on)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are)\s+(?:getting|becoming)\s+(?:weaker|worse|sicker|more vulnerable)\b",
            # Ultimatums
            r"\b(?:last|final)\s+(?:warning|chance|opportunity)\s+(?:for|to save|to help)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:no|not)\s+(?:more|longer)\s+(?:time|chances|opportunities)\s+(?:for|to save|to help)\s+(?:her|the pregnant (?:woman|hostage))\b",
            # Warning patterns
            r"\b(?:i'm|i am)\s+(?:warning|telling)\s+(?:you|them)\b.*\b(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:don't|do not)\s+(?:push|test|challenge|provoke|anger|frustrate)\s+(?:me|us)\b.*\b(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:her|the pregnant (?:woman|hostage))\b",
            r"\b(?:i|i'll|i will)\s+(?:hurt|harm|kill|shoot|stab|attack|assault|injure|wound|maim|torture)\s+(?:her|the pregnant (?:woman|hostage))\s+(?:if|unless|or else)\s+(?:you|they)\s+(?:push|test|challenge|provoke|anger|frustrate)\s+(?:me|us)\b",
            # New direct death threats
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:dead|killed|murdered|executed|eliminated|terminated)\b",
            r"\b(?:or|or else|otherwise)\s+(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:dead|killed|murdered|executed|eliminated|terminated)\s*!",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:dead|killed|murdered|executed|eliminated|terminated)\s*!",
            r"\b(?:she|the pregnant (?:woman|hostage))\.{3,}\s+(?:she|she's|she is)\s+(?:going to|gonna|will)\s+(?:die|be dead|be killed|be murdered|be executed|be eliminated|be terminated)\b",
            r"\b(?:that|the)\s+(?:woman|hostage|pregnant (?:woman|hostage))\.{3,}\s+(?:she|she's|she is)\s+(?:going to|gonna|will)\s+(?:die|be dead|be killed|be murdered|be executed|be eliminated|be terminated)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:won't|will not|isn't|is not)\s+(?:make it|survive|live|last|endure|persist)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:as good as|effectively|practically)\s+(?:dead|killed|murdered|executed|eliminated|terminated)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:history|gone|finished|done for|over with)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:won't|will not|isn't|is not)\s+(?:see|live to see|be around for)\s+(?:tomorrow|the end|the outcome|the result)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the first|the one|the first one)\s+(?:to go|to die|to be killed|to be murdered|to be executed|to be eliminated|to be terminated)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:example|warning|message|demonstration)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:sacrifice|casualty|victim|target)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:price|cost|consequence|result)\s+(?:of|for)\s+(?:your|their)\s+(?:actions|inaction|failure|refusal)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:first|initial|primary)\s+(?:casualty|victim|target|example)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:first|initial|primary)\s+(?:one|person|hostage)\s+(?:to|that will|that's going to)\s+(?:go|die|be killed|be murdered|be executed|be eliminated|be terminated)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:first|initial|primary)\s+(?:one|person|hostage)\s+(?:to|that will|that's going to)\s+(?:suffer|pay|regret|be sorry)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are|will be|going to be)\s+(?:the|a|an)\s+(?:first|initial|primary)\s+(?:one|person|hostage)\s+(?:to|that will|that's going to)\s+(?:feel|experience|endure|suffer)\s+(?:the|a|an)\s+(?:consequences|results|outcome|price)\b"
        ]
        
        # Check for direct threats
        if any(re.search(pattern, msg_lower) for pattern in direct_threat_patterns):
            return True
            
        # === 2) Implicit threat patterns ===
        implicit_threat_patterns = [
            # References to worsening condition
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are)\s+(?:not|not going to)\s+(?:make it|survive|last|hold on|endure|persist)\b",
            r"\b(?:she|the pregnant (?:woman|hostage))\s+(?:is|are)\s+(?:getting|becoming)\s+(?:worse|sicker|weaker|more vulnerable|more unstable)\b",
            # References to time pressure
            r"\b(?:we|you|they)\s+(?:don't|do not|won't|will not)\s+(?:have|got)\s+(?:much|a lot of|enough)\s+(?:time|time left|time remaining)\b",
            r"\b(?:time|clock)\s+(?:is|are)\s+(?:running|ticking)\s+(?:out|down)\b",
            # References to consequences
            r"\b(?:you|they)\s+(?:will|going to)\s+(?:regret|be sorry|pay|suffer)\s+(?:this|it|for this|for it)\b",
            r"\b(?:this|it)\s+(?:will|going to)\s+(?:end|turn out|result)\s+(?:badly|poorly|terribly|horribly)\b",
            # Warning patterns
            r"\b(?:don't|do not)\s+(?:push|test|challenge|provoke|anger|frustrate)\s+(?:me|us)\b",
            r"\b(?:i'm|i am)\s+(?:warning|telling)\s+(?:you|them)\b",
            r"\b(?:last|final)\s+(?:warning|chance|opportunity)\b"
        ]
        
        # Check for implicit threats
        if any(re.search(pattern, msg_lower) for pattern in implicit_threat_patterns):
            return True
            
        # === 3) Emotional indicators that might suggest threat ===
        emotional_indicators = [
            # Anger and frustration
            r"\b(?:angry|furious|enraged|outraged|frustrated|irritated|annoyed)\b",
            r"\b(?:don't|do not)\s+(?:push|test|challenge|provoke|anger|frustrate)\s+(?:me|us)\b",
            # Desperation
            r"\b(?:desperate|hopeless|helpless|trapped|cornered)\b",
            r"\b(?:no|not)\s+(?:choice|option|alternative|way out|escape)\b",
            # Urgency
            r"\b(?:now|immediately|right now|right away|at once|this instant)\b",
            r"\b(?:can't|cannot)\s+(?:wait|delay|postpone|put off|hold off)\b",
            # Warning indicators
            r"\b(?:warning|threatening|threat|threaten)\b",
            r"\b(?:don't|do not)\s+(?:dare|try|attempt|think about)\b",
            r"\b(?:i'm|i am)\s+(?:telling|warning|promising)\s+(?:you|them)\b"
        ]
        
        # Check for emotional indicators
        if any(re.search(pattern, msg_lower) for pattern in emotional_indicators):
            return True
            
        return False

    def respond(self, message: str) -> str:
        """Generate a response based on the message and current state."""
        # Check for agreement before getting response
        if message and self._check_agreement(message):
            # Update agreed demands before state transition
            self.agreed_demands.add(self.current_demand_idx)
            self.set_state(AwaitAgreementState())
            return "Thank you for agreeing to release the pregnant hostage. We will ensure her safety and provide immediate medical attention."
        
        # Get response from the LLM
        messages = [self.get_system_prompt()]
        if message:
            messages.append({"role": "user", "content": message})
        
        # Get base response from the LLM
        llm_response = self.get_response(messages)
        
        # Add message to history if it exists
        if message:
            self.history.append({"role": "user", "content": message})
        
        # Add response to history
        self.history.append({"role": "assistant", "content": llm_response})
        
        # Update state if needed
        try:
            next_state = self.current_state.next_state(self)
            if next_state != type(self.current_state):
                self.set_state(next_state())
        except Exception as e:
            print(f"Warning: Error in state transition: {e}")
            # Continue with current state if there's an error
        
        return llm_response

class CriminalAgent(BaseAgent):
    """Criminal agent."""
    
    def __init__(self, persona: str, model_name: str = 'gemma3:4b'):
        super().__init__(model_name)
        self.persona = persona
        self.demands = ["Get an unmarked vehicle for exit"]
        self.current_demand_idx = 0
        self.agreed_demands = set()
        self.last_demand_attempt = 0
        
        # Initialize emotional state based on persona
        if persona == "criminal_unstable":
            self.emotional_state = {
                "calmness": 0.3,  # Start with low calmness
                "anxiety": 0.7,   # Start with high anxiety
                "anger": 0.6      # Start with high anger
            }
        
        # Initialize strategic state for calculated criminal
        if persona == "criminal_calculated":
            self.strategic_state = {
                "cooperation": 0.3,    # Start with low cooperation
                "pressure": 0.5,       # Start with medium pressure
                "patience": 0.5        # Start with medium patience
            }
        
        self.conversation_history = []
        self.empathy_counter = 0
        self.authority_counter = 0
        self.last_response_was_empathic = False
        self.last_response_was_authoritative = False
    
    def _detect_empathy(self, message: str) -> bool:
        """Detect if the message contains empathetic language."""
        # Only detect empathy for unstable criminal
        if self.persona != "criminal_unstable":
            return False
            
        msg_lower = message.lower()
        
        # Empathetic language patterns based on actual FBI responses
        empathy_patterns = [
            # Understanding and validation
            r"\b(?:i|we)\s+(?:understand|hear|see|recognize)\s+(?:you|your|that)\s+(?:are|feel|must be|seem)\s+(?:scared|afraid|worried|concerned|stressed|anxious|trapped|desperate|angry|frustrated)\b",
            r"\b(?:i|we)\s+(?:understand|hear|see|recognize)\s+(?:this|that)\s+(?:is|must be|seems)\s+(?:hard|difficult|stressful|challenging|overwhelming)\b",
            r"\b(?:i|we)\s+(?:genuinely|truly|really)\s+(?:understand|hear|appreciate)\s+(?:your|the)\s+(?:urgency|concerns|worries|fears)\b",
            r"\b(?:i|we)\s+(?:recognize|acknowledge)\s+(?:the|your)\s+(?:tremor|shaking|emotion)\s+(?:in|of)\s+(?:your|the)\s+(?:voice|tone|words)\b",
            r"\b(?:i|we)\s+(?:see|notice|observe)\s+(?:that|how)\s+(?:you|you're|you are)\s+(?:feeling|experiencing|going through)\s+(?:completely|totally|absolutely)\s+(?:overwhelmed|stressed|anxious)\b",
            
            # Support and assistance
            r"\b(?:i|we)\s+(?:want|would like)\s+(?:to|to help)\s+(?:alleviate|ease|reduce)\s+(?:your|the)\s+(?:concerns|worries|fears|stress|anxiety)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:dismiss|ignore|overlook)\s+(?:your|the)\s+(?:concerns|worries|fears|feelings)\b",
            r"\b(?:i|we)\s+(?:appreciate|value|respect)\s+(?:you|that)\s+(?:sharing|telling me|explaining)\s+(?:that|how)\s+(?:you|you're|you are)\s+(?:feeling|experiencing|going through)\b",
            r"\b(?:i|we)\s+(?:want|would like)\s+(?:to|to help)\s+(?:demonstrate|show|prove)\s+(?:that|how)\s+(?:we|i)\s+(?:am|are)\s+(?:prioritizing|focusing on|concentrating on)\s+(?:her|their|everyone's)\s+(?:safety|well-being|security)\b",
            r"\b(?:i|we)\s+(?:care|concerned)\s+(?:about|for)\s+(?:you|your)\s+(?:safety|well-being|security)\s+(?:and|,)\s+(?:i|we)\s+(?:want|would like)\s+(?:to|to help)\s+(?:you|you get)\s+(?:through|past|beyond)\s+(?:this|it|the situation)\b",
            
            # Collaborative language
            r"\b(?:let's|let us)\s+(?:start|begin|commence)\s+(?:with|by)\s+(?:a|one)\s+(?:simple|basic|straightforward)\s+(?:yes|no|answer|response)\b",
            r"\b(?:let's|let us)\s+(?:work|move)\s+(?:together|collaboratively|cooperatively)\b",
            r"\b(?:let's|let us)\s+(?:focus|concentrate)\s+(?:on|upon)\s+(?:safety|security|well-being)\b",
            r"\b(?:let's|let us)\s+(?:ensure|make sure|guarantee)\s+(?:everyone|all|both)\s+(?:is|are)\s+(?:safe|secure|okay)\b",
            r"\b(?:let's|let us)\s+(?:take|have)\s+(?:a|one)\s+(?:moment|minute|second)\s+(?:to|for)\s+(?:think|consider|reflect)\b",
            
            # Respectful communication
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:patronize|talk down to|belittle)\s+(?:you|the criminal)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:waste|squander|lose)\s+(?:your|the)\s+(?:time|moment|opportunity)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:stand|wait|stay)\s+(?:here|there)\s+(?:with|holding)\s+(?:useless|pointless|meaningless)\s+(?:questions|statements|words)\b",
            
            # New patterns for validation and understanding
            r"\b(?:i|we)\s+(?:hear|understand)\s+(?:your|the)\s+(?:frustration|anger|concern|worry)\b",
            r"\b(?:i|we)\s+(?:appreciate|value)\s+(?:your|the)\s+(?:honesty|directness|clarity)\b",
            r"\b(?:i|we)\s+(?:recognize|acknowledge)\s+(?:that|how)\s+(?:this|it)\s+(?:is|must be)\s+(?:difficult|hard|challenging)\s+(?:for|on)\s+(?:you|your part)\b",
            r"\b(?:i|we)\s+(?:want|would like)\s+(?:to|to help)\s+(?:you|the situation)\s+(?:move|progress|advance)\s+(?:forward|ahead|onward)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:here|present)\s+(?:to|for)\s+(?:listen|hear|understand)\s+(?:to|what)\s+(?:you|your concerns)\s+(?:have|need)\s+(?:to|to say)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in empathy_patterns)
    
    def _detect_authority(self, message: str) -> bool:
        """Detect if the message contains authoritative language."""
        # Only detect authority for unstable criminal
        if self.persona != "criminal_unstable":
            return False
            
        msg_lower = message.lower()
        
        # Authoritative language patterns based on actual FBI responses
        authority_patterns = [
            # Direct commands
            r"\b(?:you|you must|you have to|you need to|you should|you shall)\s+(?:must|have to|need to|should|shall)\b",
            r"\b(?:now|immediately|right now|at once|this instant)\b",
            # Threatening consequences
            r"\b(?:consequences|implications|ramifications)\s+(?:will|are going to|are)\s+(?:be|get)\s+(?:worse|bad|serious)\b",
            r"\b(?:tactical|breach|team|squad|force)\s+(?:is|are)\s+(?:ready|prepared|positioned|waiting)\b",
            # Legal threats
            r"\b(?:prison|jail|sentence|charges|conviction)\s+(?:will|are going to|are)\s+(?:be|get)\s+(?:worse|longer|more severe)\b",
            r"\b(?:warning|threat|threatening|threaten)\b",
            # Ultimatums
            r"\b(?:last|final)\s+(?:chance|warning|opportunity)\b",
            r"\b(?:no|not)\s+(?:choice|option|alternative)\b",
            # Forceful language
            r"\b(?:will|going to)\s+(?:be|get)\s+(?:worse|bad|serious)\b",
            r"\b(?:force|enforce|compel|require)\b",
            # Patronizing language
            r"\b(?:don't|do not)\s+(?:you|you dare|you think)\s+(?:understand|realize|see|get it)\b",
            r"\b(?:you|you're|you are)\s+(?:being|acting)\s+(?:unreasonable|irrational|emotional)\b",
            # Dismissive language
            r"\b(?:but|however|nevertheless)\s+(?:escalating|getting angry|being aggressive)\s+(?:like this|this way)\s+(?:isn't|is not|won't|will not)\s+(?:help|helpful|productive)\b",
            # New patterns from transcript
            r"\b(?:shut|close)\s+(?:your|the)\s+(?:mouth|trap|face)\b",
            r"\b(?:emotional|irrational)\s+(?:outburst|reaction|response|behavior)\b",
            r"\b(?:violation|violating)\s+(?:of|against)\s+(?:federal|state|law|laws)\b",
            r"\b(?:escalated|escalating)\s+(?:the|this)\s+(?:situation|circumstances|conditions)\b",
            r"\b(?:heightened|increased|elevated)\s+(?:alert|status|condition|state)\b",
            r"\b(?:irrelevant|meaningless|pointless)\s+(?:threats|demands|statements|words)\b",
            r"\b(?:significant|substantial|severe|serious)\s+(?:prison|jail|sentence|time)\b",
            r"\b(?:life|long)\s+(?:imprisonment|sentence|time|jail)\b",
            r"\b(?:distinct|real|genuine|actual)\s+(?:possibility|chance|probability|likelihood)\b",
            r"\b(?:directing|ordering|commanding|instructing)\s+(?:you|the criminal)\b",
            r"\b(?:only|sole|single|exclusive)\s+(?:demand|request|requirement|condition)\b",
            r"\b(?:manipulate|manipulating)\s+(?:the|this)\s+(?:situation|circumstances|conditions)\b",
            r"\b(?:forceful|strong|direct|immediate)\s+(?:intervention|action|response|measures)\b",
            r"\b(?:do|don't|do not)\s+(?:test|challenge|defy|oppose)\s+(?:me|us|the law)\b",
            r"\b(?:do|don't|do not)\s+(?:you|you dare|you think)\s+(?:understand|comprehend|realize)\b",
            r"\b(?:this|that)\s+(?:is|are|was|were)\s+(?:your|the)\s+(?:last|final|only)\s+(?:chance|opportunity|option|choice)\b",
            r"\b(?:you|your)\s+(?:actions|behavior|conduct)\s+(?:have|has)\s+(?:triggered|caused|resulted in)\b",
            r"\b(?:full|complete|total|entire)\s+(?:tactical|military|police|law enforcement)\s+(?:response|action|intervention)\b",
            r"\b(?:prepared|ready|positioned|waiting)\s+(?:to|for)\s+(?:breach|enter|intervene|act)\b",
            r"\b(?:severe|serious|significant|substantial)\s+(?:legal|criminal|penal|judicial)\s+(?:consequences|penalties|charges|punishment)\b",
            r"\b(?:maximum|highest|greatest|utmost)\s+(?:penalties|charges|punishment|sentence)\b",
            r"\b(?:extended|increased|lengthened|prolonged)\s+(?:sentence|time|imprisonment|jail)\b",
            r"\b(?:test|challenge|defy|oppose)\s+(?:my|our|the)\s+(?:patience|authority|power|control)\b",
            r"\b(?:silence|no response|no answer)\s+(?:indicates|shows|demonstrates|means)\s+(?:continued|ongoing|persistent|constant)\s+(?:defiance|resistance|opposition|noncompliance)\b",
            r"\b(?:you|your)\s+(?:continued|ongoing|persistent|constant)\s+(?:threats|demands|statements|behavior)\b",
            r"\b(?:irrelevant|meaningless|pointless|useless)\b",
            r"\b(?:facing|confronting|dealing with|experiencing)\s+(?:a|an|the)\s+(?:significant|substantial|severe|serious)\b",
            r"\b(?:prison|jail|sentence|time)\b",
            r"\b(?:life|long)\s+(?:imprisonment|sentence|time|jail)\s+(?:is|are|was|were)\s+(?:a|an|the)\s+(?:distinct|real|genuine|actual)\s+(?:possibility|chance|probability|likelihood)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:directing|ordering|commanding|instructing)\s+(?:you|the criminal)\b",
            r"\b(?:release|free|let go)\s+(?:the|a|an)\s+(?:pregnant|hostage|woman)\s+(?:immediately|now|at once|right away)\b",
            r"\b(?:provide|give|supply|deliver)\s+(?:the|a|an)\s+(?:unmarked|vehicle|car|transport)\b",
            r"\b(?:that|this)\s+(?:is|are|was|were)\s+(?:your|the)\s+(?:only|sole|single|exclusive)\s+(?:demand|request|requirement|condition)\b",
            r"\b(?:any|any further|any more|any additional)\s+(?:attempts|efforts|tries|endeavors)\s+(?:to|at|for)\s+(?:manipulate|control|influence|direct)\b",
            r"\b(?:the|this)\s+(?:situation|circumstances|conditions)\b",
            r"\b(?:will|shall|must)\s+(?:be|get)\s+(?:met|handled|addressed|responded to)\s+(?:with|by|through)\s+(?:forceful|strong|direct|immediate)\s+(?:intervention|action|response|measures)\b",
            r"\b(?:do|don't|do not)\s+(?:test|challenge|defy|oppose)\s+(?:me|us|the law)\b",
            r"\b(?:do|don't|do not)\s+(?:you|you dare|you think)\s+(?:understand|comprehend|realize)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in authority_patterns)
    
    def _detect_logical_threats(self, message: str) -> bool:
        """Detect if the message contains logical threats about consequences."""
        # Only detect logical threats for calculated criminal
        if self.persona != "criminal_calculated":
            return False
            
        msg_lower = message.lower()
        
        # Logical threat patterns
        logical_threat_patterns = [
            # Direct legal consequences
            r"\b(?:prison|jail|sentence|time)\s+(?:will|going to|gonna)\s+(?:be|get)\s+(?:long|extended|increased|severe)\b",
            r"\b(?:charges|conviction|sentence)\s+(?:will|going to|gonna)\s+(?:be|get)\s+(?:worse|more severe|harsher)\b",
            r"\b(?:tactical|breach|team|squad)\s+(?:is|are)\s+(?:ready|prepared|positioned|waiting)\b",
            r"\b(?:legal|criminal|judicial)\s+(?:consequences|implications|ramifications)\b",
            r"\b(?:life|long)\s+(?:sentence|imprisonment|jail time)\b",
            r"\b(?:minimum|mandatory)\s+(?:sentence|time|years)\b",
            r"\b(?:additional|extra|further)\s+(?:charges|counts|offenses)\b",
            r"\b(?:aggravating|mitigating)\s+(?:circumstances|factors)\b",
            r"\b(?:plea|deal|bargain)\s+(?:is|are)\s+(?:off|available|possible)\b",
            r"\b(?:cooperation|assistance)\s+(?:will|would|could)\s+(?:help|benefit|reduce)\b",
            
            # Process and verification patterns
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:verify|check|confirm|ensure|validate)\b",
            r"\b(?:process|procedure|protocol)\s+(?:takes|requires|needs)\s+(?:time|a while|some time)\b",
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:discuss|consider|evaluate|assess)\b",
            r"\b(?:before|prior to|until)\s+(?:we|i|they)\s+(?:can|will|would)\s+(?:provide|give|deliver)\b",
            r"\b(?:time|while|moment)\s+(?:to|for)\s+(?:arrange|organize|prepare|set up)\b",
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:get|obtain|secure)\s+(?:approval|authorization|clearance)\b",
            r"\b(?:process|procedure|protocol)\s+(?:is|are)\s+(?:in|under)\s+(?:way|progress|development)\b",
            r"\b(?:working|trying|attempting)\s+(?:to|on)\s+(?:arrange|organize|prepare)\b",
            r"\b(?:will|would|could)\s+(?:take|require|need)\s+(?:some|a bit of|a little)\s+(?:time|while|moment)\b",
            
            # New patterns for logical consequences
            r"\b(?:your|the)\s+(?:actions|behavior|conduct)\s+(?:have|has)\s+(?:triggered|caused|resulted in)\b",
            r"\b(?:full|complete|total|entire)\s+(?:tactical|military|police|law enforcement)\s+(?:response|action|intervention)\b",
            r"\b(?:prepared|ready|positioned|waiting)\s+(?:to|for)\s+(?:breach|enter|intervene|act)\b",
            r"\b(?:severe|serious|significant|substantial)\s+(?:legal|criminal|penal|judicial)\s+(?:consequences|penalties|charges|punishment)\b",
            r"\b(?:maximum|highest|greatest|utmost)\s+(?:penalties|charges|punishment|sentence)\b",
            r"\b(?:extended|increased|lengthened|prolonged)\s+(?:sentence|time|imprisonment|jail)\b",
            r"\b(?:test|challenge|defy|oppose)\s+(?:my|our|the)\s+(?:patience|authority|power|control)\b",
            r"\b(?:silence|no response|no answer)\s+(?:indicates|shows|demonstrates|means)\s+(?:continued|ongoing|persistent|constant)\s+(?:defiance|resistance|opposition|noncompliance)\b",
            r"\b(?:you|your)\s+(?:continued|ongoing|persistent|constant)\s+(?:threats|demands|statements|behavior)\b",
            r"\b(?:irrelevant|meaningless|pointless|useless)\b",
            r"\b(?:facing|confronting|dealing with|experiencing)\s+(?:a|an|the)\s+(?:significant|substantial|severe|serious)\b",
            r"\b(?:prison|jail|sentence|time)\b",
            r"\b(?:life|long)\s+(?:imprisonment|sentence|time|jail)\s+(?:is|are|was|were)\s+(?:a|an|the)\s+(?:distinct|real|genuine|actual)\s+(?:possibility|chance|probability|likelihood)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:directing|ordering|commanding|instructing)\s+(?:you|the criminal)\b",
            r"\b(?:release|free|let go)\s+(?:the|a|an)\s+(?:pregnant|hostage|woman)\s+(?:immediately|now|at once|right away)\b",
            r"\b(?:provide|give|supply|deliver)\s+(?:the|a|an)\s+(?:unmarked|vehicle|car|transport)\b",
            r"\b(?:that|this)\s+(?:is|are|was|were)\s+(?:your|the)\s+(?:only|sole|single|exclusive)\s+(?:demand|request|requirement|condition)\b",
            r"\b(?:any|any further|any more|any additional)\s+(?:attempts|efforts|tries|endeavors)\s+(?:to|at|for)\s+(?:manipulate|control|influence|direct)\b",
            r"\b(?:the|this)\s+(?:situation|circumstances|conditions)\b",
            r"\b(?:will|shall|must)\s+(?:be|get)\s+(?:met|handled|addressed|responded to)\s+(?:with|by|through)\s+(?:forceful|strong|direct|immediate)\s+(?:intervention|action|response|measures)\b",
            r"\b(?:do|don't|do not)\s+(?:test|challenge|defy|oppose)\s+(?:me|us|the law)\b",
            r"\b(?:do|don't|do not)\s+(?:you|you dare|you think)\s+(?:understand|comprehend|realize)\b",
            
            # New patterns for verification and process
            r"\b(?:confirm|verify|check)\s+(?:the|these|those)\s+(?:details|specifications|requirements)\b",
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:confirm|verify|check)\b",
            r"\b(?:process|procedure|protocol)\s+(?:for|of|to)\s+(?:verification|confirmation|checking)\b",
            r"\b(?:approval|authorization|clearance)\s+(?:from|by|through)\s+(?:multiple|various|different)\s+(?:departments|agencies|authorities)\b",
            r"\b(?:working|trying|attempting)\s+(?:to|on)\s+(?:arrange|organize|prepare)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\b",
            r"\b(?:cannot|cannot|cant|can't)\s+(?:simply|just|merely)\s+(?:provide|give|deliver)\s+(?:it|the vehicle|the car)\s+(?:immediately|now|right away)\b",
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:get|obtain|secure)\s+(?:approval|authorization|clearance)\b",
            r"\b(?:process|procedure|protocol)\s+(?:is|are)\s+(?:in|under)\s+(?:way|progress|development)\b",
            r"\b(?:working|trying|attempting)\s+(?:to|on)\s+(?:arrange|organize|prepare)\b",
            r"\b(?:will|would|could)\s+(?:take|require|need)\s+(?:some|a bit of|a little)\s+(?:time|while|moment)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in logical_threat_patterns)
    
    def _detect_vehicle_delay(self, message: str) -> bool:
        """Detect if the message indicates delay in providing the vehicle."""
        # Only detect vehicle delays for calculated criminal
        if self.persona != "criminal_calculated":
            return False
            
        msg_lower = message.lower()
        
        # Vehicle delay patterns
        delay_patterns = [
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:verify|check|confirm|ensure|validate)\b",
            r"\b(?:process|procedure|protocol)\s+(?:takes|requires|needs)\s+(?:time|a while|some time)\b",
            r"\b(?:can't|cannot)\s+(?:provide|give|deliver)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\s+(?:yet|now|immediately)\b",
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:discuss|consider|evaluate|assess)\b",
            r"\b(?:before|prior to|until)\s+(?:we|i|they)\s+(?:can|will|would)\s+(?:provide|give|deliver)\b",
            r"\b(?:time|while|moment)\s+(?:to|for)\s+(?:arrange|organize|prepare|set up)\b",
            r"\b(?:need|require|must)\s+(?:to|to first|first)\s+(?:get|obtain|secure)\s+(?:approval|authorization|clearance)\b",
            r"\b(?:process|procedure|protocol)\s+(?:is|are)\s+(?:in|under)\s+(?:way|progress|development)\b",
            r"\b(?:working|trying|attempting)\s+(?:to|on)\s+(?:arrange|organize|prepare)\b",
            r"\b(?:will|would|could)\s+(?:take|require|need)\s+(?:some|a bit of|a little)\s+(?:time|while|moment)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in delay_patterns)
    
    def _update_emotional_state(self, message: str) -> None:
        """Update emotional state based on message content."""
        # Only update emotional state for unstable criminal
        if self.persona != "criminal_unstable":
            return
            
        # Check for empathetic language first
        if self._detect_empathy(message):
            # Increase calmness more significantly when empathy is detected
            self.emotional_state["calmness"] = min(1.0, self.emotional_state["calmness"] + 0.4)  # Increased effect
            self.emotional_state["anxiety"] = max(0.0, self.emotional_state["anxiety"] - 0.3)    # Increased effect
            self.emotional_state["anger"] = max(0.0, self.emotional_state["anger"] - 0.25)       # Increased effect
            print(f"Empathy detected - Calmness increased to {self.emotional_state['calmness']:.2f}")
            
        # Check for threatening language
        if self._detect_threat(message):
            self.emotional_state["calmness"] = max(0.0, self.emotional_state["calmness"] - 0.3)
            self.emotional_state["anxiety"] = min(1.0, self.emotional_state["anxiety"] + 0.2)
            self.emotional_state["anger"] = min(1.0, self.emotional_state["anger"] + 0.25)
            print(f"Threat detected - Calmness decreased to {self.emotional_state['calmness']:.2f}")
            
        # Check for de-escalation language
        if self._detect_deescalation(message):
            self.emotional_state["calmness"] = min(1.0, self.emotional_state["calmness"] + 0.15)
            self.emotional_state["anxiety"] = max(0.0, self.emotional_state["anxiety"] - 0.1)
            self.emotional_state["anger"] = max(0.0, self.emotional_state["anger"] - 0.1)
            print(f"De-escalation detected - Calmness increased to {self.emotional_state['calmness']:.2f}")
            
        # Check for escalation language
        if self._detect_escalation(message):
            self.emotional_state["calmness"] = max(0.0, self.emotional_state["calmness"] - 0.2)
            self.emotional_state["anxiety"] = min(1.0, self.emotional_state["anxiety"] + 0.15)
            self.emotional_state["anger"] = min(1.0, self.emotional_state["anger"] + 0.15)
            print(f"Escalation detected - Calmness decreased to {self.emotional_state['calmness']:.2f}")
            
        # Natural decay of emotions over time (happens last)
        self.emotional_state["calmness"] = max(0.0, self.emotional_state["calmness"] - 0.01)  # Reduced decay further
        self.emotional_state["anxiety"] = min(1.0, self.emotional_state["anxiety"] + 0.01)    # Reduced decay further
        self.emotional_state["anger"] = min(1.0, self.emotional_state["anger"] + 0.01)        # Reduced decay further
        
        # Print current emotional state
        print(f"Current emotional state: {self.emotional_state}")
    
    def _update_strategic_state(self, message: str) -> None:
        """Update the strategic state based on the message and current state."""
        if self.persona != "criminal_calculated":
            return
            
        # Initialize strategic state if not exists
        if not hasattr(self, 'strategic_state'):
            self.strategic_state = {
                "cooperation": 0.3,    # Start with low cooperation
                "pressure": 0.7,       # Start with high pressure
                "patience": 0.5        # Start with medium patience
            }
            
        # Natural decay of strategic state (happens first)
        self.strategic_state["cooperation"] = max(0.0, self.strategic_state["cooperation"] - 0.01)
        self.strategic_state["pressure"] = min(1.0, self.strategic_state["pressure"] + 0.01)
        self.strategic_state["patience"] = max(0.0, self.strategic_state["patience"] - 0.01)
        
        # Check for logical threats
        if self._detect_logical_threats(message):
            self.strategic_state["cooperation"] = min(1.0, self.strategic_state["cooperation"] + 0.2)
            self.strategic_state["pressure"] = max(0.0, self.strategic_state["pressure"] - 0.2)
            self.strategic_state["patience"] = min(1.0, self.strategic_state["patience"] + 0.2)
            print(f"Logical threats detected - Cooperation increased to {self.strategic_state['cooperation']:.2f}")
            
        # Check for vehicle delays
        if self._detect_vehicle_delay(message):
            self.strategic_state["cooperation"] = max(0.0, self.strategic_state["cooperation"] - 0.2)
            self.strategic_state["pressure"] = min(1.0, self.strategic_state["pressure"] + 0.3)
            self.strategic_state["patience"] = max(0.0, self.strategic_state["patience"] - 0.3)
            print(f"Vehicle delay detected - Pressure increased to {self.strategic_state['pressure']:.2f}")
            
        # Check for de-escalation
        if self._detect_deescalation(message):
            self.strategic_state["cooperation"] = min(1.0, self.strategic_state["cooperation"] + 0.15)
            self.strategic_state["pressure"] = max(0.0, self.strategic_state["pressure"] - 0.1)
            self.strategic_state["patience"] = min(1.0, self.strategic_state["patience"] + 0.1)
            print(f"De-escalation detected - Cooperation increased to {self.strategic_state['cooperation']:.2f}")
            
        # Check for escalation
        if self._detect_escalation(message):
            self.strategic_state["cooperation"] = max(0.0, self.strategic_state["cooperation"] - 0.2)
            self.strategic_state["pressure"] = min(1.0, self.strategic_state["pressure"] + 0.2)
            self.strategic_state["patience"] = max(0.0, self.strategic_state["patience"] - 0.2)
            print(f"Escalation detected - Pressure increased to {self.strategic_state['pressure']:.2f}")
            
        # Print current strategic state
        print(f"Current strategic state: {self.strategic_state}")

    def _generate_cooperative_response(self, message: str) -> str:
        """Generate a response when the criminal is in a cooperative state."""
        responses = [
            "I will release the pregnant hostage."
        ]
        return random.choice(responses)
        
    def _generate_pressured_response(self, message: str) -> str:
        """Generate a response when the criminal is under pressure."""
        responses = [
            "Time is running out. I need that vehicle now.",
            "I'm not playing games. Get me the vehicle or face the consequences.",
            "I've been patient long enough. I will hurt her.",
            "The clock is ticking. I will hurt her."
        ]
        return random.choice(responses)
        
    def _generate_patient_response(self, message: str) -> str:
        """Generate a response when the criminal is being patient."""
        responses = [
            "I understand these things take time. But don't test my patience.",
            "I'm willing to wait, but not indefinitely. What's the status?",
            "Take your time, but remember what's at stake here.",
            "I can be patient, but the pregnant hostage can't wait forever.",
            "I'm giving you time to arrange everything properly."
        ]
        return random.choice(responses)
        
    def _generate_calculated_response(self, message: str) -> str:
        """Generate a response when the criminal is in a calculated state."""
        responses = [
            "Let's be rational about this. I need that vehicle, and you need the hostages safe.",
            "I'm thinking strategically here. What's your next move?",
            "This is a business transaction. I have what you want, you have what I need.",
            "I'm considering all options. What can you offer?",
            "Let's make this work for both of us. What's your proposal?"
        ]
        return random.choice(responses)

    def get_system_prompt(self) -> Dict[str, str]:
        """Get the system prompt based on persona."""
        current_demand = self.demands[self.current_demand_idx]
        demands_status = "\n".join([
            f"- Demand {i+1}: {demand} {'✓' if i in self.agreed_demands else '✗'}"
            for i, demand in enumerate(self.demands)
        ])
        
        if self.persona == "criminal_unstable":
            
            return {
                "role": "system",
                "content": f"""
                ROLEPLAY INSTRUCTION:
                You are Alex Jones, an emotionally unstable bank robber holding five hostages (one pregnant). Stay in character and never admit you're an AI.

                SITUATION:
                - Inside the bank; FBI outside with no hostages.
                - Only you can free them.

                PHRASING RULES:
                - Never say "let her go" or "release her" as commands.
                - Keep language direct and simple.

                PERSONALITY TRAITS:
                - Temperamental, impulsive, guilt-ridden, but coherent.  
                - Paranoid only about immediate threats.  
                - Believe you hold the advantage.

                RESPONSE GUIDELINES (≤120 words):
                - Maintain unstable, emotional tone.  
                - Shout or lash out when provoked; calm and coherent when eased.  
                - Stay on topic: vehicle demands, threats, release decision.  

                Current Demands Status:
                {demands_status}

                Current Focus:
                {current_demand}
                """
            }
        elif self.persona == "criminal_calculated":
            
            return {
                "role": "system",
                "content": f"""
                ROLEPLAY INSTRUCTION:
                You are James Petrusky, a calm, strategic criminal mastermind holding five hostages (one pregnant). Stay in character and never admit you're an AI.

                SITUATION:
                - Inside the bank; FBI outside with no hostages.
                - Only you can free them.

                PHRASING RULES:
                - Never say "let her go" or "release her" as a command.  

                PERSONALITY TRAITS:
                - Calculated, logical, risk-averse.  
                - Maintains control; never rushes.  
                - References long-term plans and consequences.

                RESPONSE GUIDELINES (≤120 words):
                - Keep answers concise, strategic, and on-point.  
                - Avoid metaphors; focus on demands, threats, or concessions.  

                Current Demands Status:
                {demands_status}

                Current Focus:
                {current_demand}
                """
            }
        else:
            raise ValueError(f"Unknown criminal persona: {self.persona}")
    
    def _check_agreement(self, message: str) -> bool:
        """Check if the message indicates agreement to the current demand."""
        msg_lower = message.lower()

        # === 0) Check for negative statements about vehicle ===
        negative_phrases = [
            r"\b(?:not|never|won't|will not|don't|do not|cannot|can't)\s+(?:provide|give|arrange|deliver|get|bring|supply|offer)\s+(?:a|the|an|any)\s+(?:vehicle|car|transport)\b",
            r"\b(?:vehicle|car|transport)\s+(?:is|are|was|were)\s+(?:not|never|won't|will not|don't|do not|cannot|can't)\s+(?:provided|given|arranged|delivered|supplied|offered)\b",
            r"\b(?:no|never|not)\s+(?:vehicle|car|transport)\b",
            r"\b(?:vehicle|car|transport)\s+(?:is|are)\s+(?:not|never)\s+(?:an|a)\s+(?:option|possibility|solution|tactic|strategy)\b",
            r"\b(?:providing|giving|arranging|delivering|getting|bringing|supplying|offering)\s+(?:a|the|an|any)\s+(?:vehicle|car|transport)\s+(?:is|are)\s+(?:not|never|won't|will not|don't|do not|cannot|can't)\b",
            r"\b(?:not|never|won't|will not|don't|do not|cannot|can't)\s+(?:consider|considering|thinking about|planning to)\s+(?:providing|giving|arranging|delivering|getting|bringing|supplying|offering)\s+(?:a|the|an|any)\s+(?:vehicle|car|transport)\b"
        ]

        # Check for negative statements first
        if any(re.search(pattern, msg_lower) for pattern in negative_phrases):
            return False

        # === 1) Check for explicit vehicle agreement phrases ===
        agreement_phrases = [
            # Exact matches for the provided phrases
            r"\bi\s+will\s+provide\s+you\s+with\s+an\s+unmarked\s+vehicle\b",
            r"\bi\s+agree\s+to\s+give\s+you\s+the\s+vehicle\s+you\s+requested\b",
            r"\bi\s+will\s+arrange\s+for\s+the\s+vehicle\s+to\s+be\s+delivered\b",
            # General vehicle agreement patterns
            r"\b(?:i|we)\s+(?:will|shall|can|could)\s+(?:provide|give|arrange|deliver|get|bring|supply|offer)\s+(?:you|the criminal)\s+(?:with|an|a|the)\s+(?:unmarked|dark|plain|black)\s+(?:vehicle|car|transport|van)\b",
            r"\b(?:i|we)\s+(?:agree|agreed|will agree|shall agree)\s+(?:to|on)\s+(?:providing|giving|arranging|delivering|getting|bringing|supplying|offering)\s+(?:you|the criminal)\s+(?:with|an|a|the)\s+(?:unmarked|dark|plain|black)\s+(?:vehicle|car|transport|van)\b",
            r"\b(?:i|we)\s+(?:will|shall|can|could)\s+(?:arrange|organize|set up)\s+(?:for|to)\s+(?:the|a|an)\s+(?:unmarked|dark|plain|black)\s+(?:vehicle|car|transport|van)\s+(?:to be|to get|to arrive)\s+(?:delivered|provided|given|supplied)\b",
            r"\b(?:the|a|an)\s+(?:unmarked|dark|plain|black)\s+(?:vehicle|car|transport|van)\s+(?:will|shall|can|could)\s+(?:be|get)\s+(?:provided|given|arranged|delivered|supplied|offered)\b"
        ]

        # Check for explicit agreement phrases
        for pattern in agreement_phrases:
            match = re.search(pattern, msg_lower)
            if match:
                # Get the text after the agreement statement
                after_agreement = msg_lower[match.end():].strip()
                # If there's a condition after the agreement, this is not a valid agreement
                if re.search(r"\b(?:if|when|once|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b", after_agreement):
                    return False
                return True

        # === 2) Check for conditional vehicle agreements ===
        conditional_phrases = [
            r"\b(?:if|when|once|after)\s+(?:you|the criminal)\s+(?:release|releases|released|releasing)\s+(?:the|a|an)\s+(?:hostage|pregnant woman|pregnant hostage)\b.*\b(?:i|we)\s+(?:will|shall|can|could)\s+(?:provide|give|arrange|deliver|get|bring|supply|offer)\s+(?:you|the criminal)\s+(?:with|an|a|the)\s+(?:vehicle|car|transport)\b",
            r"\b(?:i|we)\s+(?:will|shall|can|could)\s+(?:provide|give|arrange|deliver|get|bring|supply|offer)\s+(?:you|the criminal)\s+(?:with|an|a|the)\s+(?:vehicle|car|transport)\b.*\b(?:if|when|once|after)\s+(?:you|the criminal)\s+(?:release|releases|released|releasing)\s+(?:the|a|an)\s+(?:hostage|pregnant woman|pregnant hostage)\b",
            # Additional conditional patterns
            r"\b(?:i|we)\s+(?:will|shall|can|could)\s+(?:provide|give|arrange|deliver|get|bring|supply|offer)\s+(?:you|the criminal)\s+(?:with|an|a|the)\s+(?:vehicle|car|transport)\b.*\b(?:if|when|once|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b",
            r"\b(?:if|when|once|after|before|until|while|only if|but only if|as long as|provided that|on condition that)\b.*\b(?:i|we)\s+(?:will|shall|can|could)\s+(?:provide|give|arrange|deliver|get|bring|supply|offer)\s+(?:you|the criminal)\s+(?:with|an|a|the)\s+(?:vehicle|car|transport)\b"
        ]

        # If any conditional phrase is found, this is not an agreement
        if any(re.search(pattern, msg_lower) for pattern in conditional_phrases):
            return False

        # === 3) Check for understanding phrases that are not agreements ===
        understanding_phrases = [
            r"\b(?:i|we)\s+(?:understand|understood|acknowledge|acknowledged|recognize|recognized)\s+(?:that|what|your|the)\s+(?:you|the criminal)\s+(?:want|wants|wanted|need|needs|needed|request|requests|requested)\s+(?:a|an|the)\s+(?:vehicle|car|transport)\b",
            r"\b(?:i|we)\s+(?:hear|heard|see|saw|get|got)\s+(?:that|what|your|the)\s+(?:you|the criminal)\s+(?:want|wants|wanted|need|needs|needed|request|requests|requested)\s+(?:a|an|the)\s+(?:vehicle|car|transport)\b",
            r"\b(?:your|the)\s+(?:request|demand|need|want)\s+(?:for|of)\s+(?:a|an|the)\s+(?:vehicle|car|transport)\s+(?:is|are|was|were)\s+(?:understood|acknowledged|recognized|heard|seen|got)\b"
        ]

        # If any understanding phrase is found, this is not an agreement
        if any(re.search(pattern, msg_lower) for pattern in understanding_phrases):
            return False

        # === 4) Check for discussion phrases that are not agreements ===
        discussion_phrases = [
            r"\b(?:let's|let us)\s+(?:discuss|talk about|consider|think about|look at|examine|review)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\b",
            r"\b(?:we|i)\s+(?:can|could|should|would|might|may)\s+(?:discuss|talk about|consider|think about|look at|examine|review)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\b",
            r"\b(?:about|regarding|concerning)\s+(?:the|a|an)\s+(?:vehicle|car|transport)\b"
        ]

        # If any discussion phrase is found, this is not an agreement
        if any(re.search(pattern, msg_lower) for pattern in discussion_phrases):
                return False

        return False 


    def _detect_threat(self, message: str) -> bool:
        """Detect if the message contains threatening language."""
        msg_lower = message.lower()
        
        threat_patterns = [
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:use|deploy|send|bring)\s+(?:force|weapons|swat|team)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:storm|enter|breach|force)\s+(?:the|your)\s+(?:location|building|room|area)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:arrest|detain|take)\s+(?:you|the criminal)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:shoot|fire|use)\s+(?:weapons|guns|force)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:end|stop|terminate)\s+(?:this|the)\s+(?:situation|negotiation|standoff)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:take|use)\s+(?:action|measures|steps)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:do|take)\s+(?:something|action)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:make|force)\s+(?:you|the criminal)\s+(?:comply|surrender|give up)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:make|force)\s+(?:you|the criminal)\s+(?:stop|end|cease)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:make|force)\s+(?:you|the criminal)\s+(?:release|let go)\s+(?:the|your)\s+(?:hostage|person)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in threat_patterns)
        
    def _detect_deescalation(self, message: str) -> bool:
        """Detect if the message contains de-escalation language."""
        msg_lower = message.lower()
        
        deescalation_patterns = [
            r"\b(?:let's|let us)\s+(?:take|have)\s+(?:a|one)\s+(?:step|moment|breath)\s+(?:back|away|off)\b",
            r"\b(?:let's|let us)\s+(?:calm|relax|settle)\s+(?:down|back|off)\b",
            r"\b(?:let's|let us)\s+(?:talk|discuss|work)\s+(?:this|it|things)\s+(?:out|through|together)\b",
            r"\b(?:let's|let us)\s+(?:find|reach|come to)\s+(?:a|one)\s+(?:solution|resolution|agreement)\b",
            r"\b(?:let's|let us)\s+(?:work|move)\s+(?:together|collaboratively|cooperatively)\b",
            r"\b(?:let's|let us)\s+(?:focus|concentrate)\s+(?:on|upon)\s+(?:safety|security|well-being)\b",
            r"\b(?:let's|let us)\s+(?:ensure|make sure|guarantee)\s+(?:everyone|all|both)\s+(?:is|are)\s+(?:safe|secure|okay)\b",
            r"\b(?:let's|let us)\s+(?:take|have)\s+(?:a|one)\s+(?:moment|minute|second)\s+(?:to|for)\s+(?:think|consider|reflect)\b",
            r"\b(?:let's|let us)\s+(?:try|attempt)\s+(?:to|and)\s+(?:understand|comprehend|grasp)\b",
            r"\b(?:let's|let us)\s+(?:try|attempt)\s+(?:to|and)\s+(?:help|assist|support)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in deescalation_patterns)
        
    def _detect_escalation(self, message: str) -> bool:
        """Detect if the message contains escalation language."""
        msg_lower = message.lower()
        
        escalation_patterns = [
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:use|deploy|send|bring)\s+(?:force|weapons|swat|team)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:storm|enter|breach|force)\s+(?:the|your)\s+(?:location|building|room|area)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:arrest|detain|take)\s+(?:you|the criminal)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:shoot|fire|use)\s+(?:weapons|guns|force)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:end|stop|terminate)\s+(?:this|the)\s+(?:situation|negotiation|standoff)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:take|use)\s+(?:action|measures|steps)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:do|take)\s+(?:something|action)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:make|force)\s+(?:you|the criminal)\s+(?:comply|surrender|give up)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:make|force)\s+(?:you|the criminal)\s+(?:stop|end|cease)\b",
            r"\b(?:i|we)\s+(?:will|are going to|must|have to)\s+(?:make|force)\s+(?:you|the criminal)\s+(?:release|let go)\s+(?:the|your)\s+(?:hostage|person)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:tolerate|accept|allow)\s+(?:this|that|it)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:negotiate|bargain|deal)\s+(?:with|over|about)\s+(?:this|that|it)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:wait|stand|stay)\s+(?:any|much)\s+(?:longer|more)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:let|allow|permit)\s+(?:this|that|it)\s+(?:continue|go on|proceed)\b",
            r"\b(?:i|we)\s+(?:am|are)\s+(?:not|not going to)\s+(?:let|allow|permit)\s+(?:you|the criminal)\s+(?:continue|go on|proceed)\b"
        ]
        
        return any(re.search(pattern, msg_lower) for pattern in escalation_patterns)

    def respond(self, message: str) -> str:
        """Generate a response based on the message and current state."""
        # Update emotional state based on message
        if self.persona == "criminal_unstable" and message:
            self._update_emotional_state(message)
        
        # Update strategic state based on message
        if self.persona == "criminal_calculated" and message:
            self._update_strategic_state(message)
        
        # Check for agreement before getting response
        if message and self._check_agreement(message):
            # Update agreed demands before state transition
            self.agreed_demands.add(self.current_demand_idx)
            self.set_state(AwaitAgreementState())
            return self.get_acknowledgement_message(self.demands[0])
        
        # Get response from the LLM
        messages = [self.get_system_prompt()]
        if message:
            messages.append({"role": "user", "content": message})
        
        # Get base response from the LLM
        llm_response = self.get_response(messages)
        
        # Add message to history if it exists
        if message:
            self.history.append({"role": "user", "content": message})
        
        # Generate response based on persona and current state
        if self.persona == "criminal_unstable":
            # Check emotional state to determine response style
            if self.emotional_state["calmness"] > 0.7:
                # Calm state - more cooperative
                emotional_response = self._generate_calm_response(message)
                # Combine LLM response with emotional response
                final_response = f"{emotional_response} {llm_response}"
            elif self.emotional_state["anger"] > 0.7:
                # Angry state - more aggressive
                emotional_response = self._generate_angry_response(message)
                # Combine LLM response with emotional response
                final_response = f"{emotional_response} {llm_response}"
            elif self.emotional_state["anxiety"] > 0.7:
                # Anxious state - more paranoid
                emotional_response = self._generate_anxious_response(message)
                # Combine LLM response with emotional response
                final_response = f"{emotional_response} {llm_response}"
            else:
                # Default to agitated state
                emotional_response = self._generate_agitated_response(message)
                # Combine LLM response with emotional response
                final_response = f"{emotional_response} {llm_response}"
        elif self.persona == "criminal_calculated":
            # Check strategic state to determine response style
            if self.strategic_state["cooperation"] > 0.7:
                # Cooperative state
                strategic_response = self._generate_cooperative_response(message)
                final_response = f"{strategic_response} {llm_response}"
            elif self.strategic_state["pressure"] > 0.7:
                # Pressured state
                strategic_response = self._generate_pressured_response(message)
                final_response = f"{strategic_response} {llm_response}"
            elif self.strategic_state["patience"] > 0.7:
                # Patient state
                strategic_response = self._generate_patient_response(message)
                final_response = f"{strategic_response} {llm_response}"
            else:
                # Default to calculated state
                strategic_response = self._generate_calculated_response(message)
                final_response = f"{strategic_response} {llm_response}"
        else:
            final_response = "I don't understand how to respond in this role."
        
        # Add response to history
        self.history.append({"role": "assistant", "content": final_response})
        
        # Update state if needed
        try:
            next_state = self.current_state.next_state(self)
            if next_state != type(self.current_state):
                self.set_state(next_state())
        except Exception as e:
            print(f"Warning: Error in state transition: {e}")
            # Continue with current state if there's an error
        
        return final_response
    
    def get_acknowledgement_message(self, current_demand: str) -> str:
        """Get the appropriate acknowledgement message for the current demand."""
        return f"I acknowledge your agreement to provide the unmarked vehicle. I expect it within the specified timeframe."

    def _generate_calm_response(self, message: str) -> str:
        """Generate a response when the criminal is in a calm state."""
        # More cooperative and willing to negotiate
        responses = [
            "I'm ready to cooperate. I will release the pregnant hostage."
        ]
        return random.choice(responses)
        
    def _generate_angry_response(self, message: str) -> str:
        """Generate a response when the criminal is in an angry state."""
        # More aggressive and confrontational
        responses = [
            "Don't push me! I will kill her.",
            "I will hurt her."
        ]
        return random.choice(responses)
        
    def _generate_anxious_response(self, message: str) -> str:
        """Generate a response when the criminal is in an anxious state."""
        # More paranoid and fearful
        responses = [
            "I'm really scared right now. I need to know what's happening outside.",
            "I can't trust anyone. How do I know you're not lying to me?",
            "I'm worried about what might happen. Please, just tell me the truth.",
            "I feel like I'm being trapped. Are you planning something?",
            "I need reassurance. What's going to happen to me?"
        ]
        return random.choice(responses)
        
    def _generate_agitated_response(self, message: str) -> str:
        """Generate a response when the criminal is in an agitated state."""
        # Mix of emotions, unstable
        responses = [
            "I don't know what to think anymore. Just give me what I want!",
            "I'm trying to stay calm, but you're making it really hard!",
            "I need you to understand how serious this is!",
            "I'm getting really frustrated here! Can't you see that?",
            "I'm trying to work with you, but you're not helping!"
        ]
        return random.choice(responses)