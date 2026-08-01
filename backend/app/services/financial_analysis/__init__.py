"""Financial Analysis Engine.

Transforms a normalised :class:`FinancialStatement` into enterprise financial
intelligence: ratios, health scores, insights, risk flags, recommendations and
multi-period trends.

This package is *additive* and deterministic. It does not use ML or LLMs and it
does not alter the credit scorecard (``services/enterprise_assessment``)
in any way; the scorecard remains the authoritative credit-risk layer while this
package is the authoritative financial-intelligence layer.
"""
