# Knowing where not to look: a summary of the note

The note proposes query- and source-resolved confidence for agents. Four sources: P (the model's
weights), W (the open web and the user's turns), K (a curated knowledge base) and M (the system's
memory). Before execution, a query-side analysis (KAP: knowledge, ambiguity, prediction) predicts,
for each source, a reliability r (correct if the answer is in its corpus) and a ghost mass g (the
answer is not in its corpus). Question quality enters first as a hurdle with probability pi(q).

Sample-agreement confidence converges to the agent's own proposal distribution, not to the truth.
Rare passages hold the answer where the agent seldom goes; ghost passages hold it nowhere. The
decision rule is answer, qualify, ask or abstain.
