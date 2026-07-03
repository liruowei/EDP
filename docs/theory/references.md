# Academic References

This document lists the academic references that form the theoretical
foundation of the **EDP (Expectation Domain Perception Method)** framework.

> All works below are peer-reviewed academic literature in probability theory,
> Bayesian inference, forecasting, and information aggregation. They are cited
> here purely for theoretical attribution. EDP itself is for academic research
> and education only.

---

## Core Methodology

### Shin Normalization — True Probability Extraction

**Shin, H.S. (1992).** "Prices of State-Contingent Claims with Insider Traders,
and the Favourite-Longshot Bias." *The Economic Journal*, 102(411), 426-435.

DOI: [10.2307/2234526](https://doi.org/10.2307/2234526)

> Establishes the mathematical framework for decomposing quoted state-contingent
> prices into true probability, margin, and information-asymmetry components.
> EDP's L1 layer uses Shin's iterative method to remove the bookmaker margin
> ("overround") and recover underlying probabilities.

---

### Bayesian Inference

**Gelman, A., Carlin, J.B., Stern, H.S., Dunson, D.B., Vehtari, A. & Rubin, D.B. (2013).**
*Bayesian Data Analysis* (3rd ed.). CRC Press.

DOI: [10.1201/b16018](https://doi.org/10.1201/b16018)

> Foundational text for Bayesian inference. EDP's L2 layer uses the
> Beta-Binomial conjugate model for sequential posterior updating, and L4 uses
> Bayesian log-odds accumulation for multi-source fusion.

---

### Glicko-2 Rating System — Dynamic Strength Modeling

**Glickman, M.E. (2001).** "Dynamic Paired Comparison Models with Stochastic
Variances." *Journal of Applied Statistics*, 28(6), 673-689.

DOI: [10.1080/02664760120059219](https://doi.org/10.1080/02664760120059219)

> Introduces the **Glicko-2** system: an improvement over Glicko/Elo that adds
> a rating deviation (RD) and a stochastic volatility parameter (σ). EDP's L2
> layer uses Glicko-2 for dynamic strength modeling of paired-comparison
> entities (e.g. sports teams).

> Note: Glickman (1999), *Applied Statistics* 48(3):377-394, describes the
> earlier **Glicko** (Glicko-1) system without volatility. EDP implements
> Glicko-2 and therefore cites the 2001 paper.

---

### Kelly Criterion — Optimal Resource Allocation

**Kelly, J.L. (1956).** "A New Interpretation of Information Rate." *Bell System
Technical Journal*, 35(4), 917-926.

DOI: [10.1002/j.1538-7305.1956.tb03809.x](https://doi.org/10.1002/j.1538-7305.1956.tb03809.x)

> Original paper on maximizing the expected logarithmic growth rate. EDP's L5
> layer adapts the Kelly criterion (in fractional form, default quarter-Kelly)
> as a *research-only* signal-strength-based allocation heuristic. The output
> is NOT investment advice.

---

### Modern Portfolio Theory — Diversification

**Markowitz, H. (1952).** "Portfolio Selection." *The Journal of Finance*, 7(1),
77-91.

DOI: [10.2307/2975974](https://doi.org/10.2307/2975974)

> Foundation of diversification theory. EDP's L5 layer adapts Markowitz-style
> concentration constraints and diversification ratios to reduce variance in
> the allocation output.

---

### Time-Series Momentum

**Moskowitz, T.J., Ooi, Y.H. & Pedersen, L.H. (2012).** "Time Series Momentum."
*Journal of Financial Economics*, 104(2), 228-250.

DOI: [10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)

> Provides the theoretical basis for momentum-based amplification: signals with
> positive momentum tend to persist. EDP's L3 layer uses weighted momentum
> scores, velocity, and acceleration of probability flows.

---

### Information Cascades

**Banerjee, A.V. (1992).** "A Simple Model of Herd Behavior." *The Quarterly
Journal of Economics*, 107(3), 797-817.

DOI: [10.2307/2118364](https://doi.org/10.2307/2118364)

> Behavioral-economics foundation for why probability flows cascade through
> adjacent outcomes. EDP's L3 layer implements BFS-based cascade detection on
> the EventGraph.

---

### Opinion Pooling — Multi-Source Fusion

**Cooke, R.M. (1991).** *Experts in Uncertainty: Opinion and Subjective
Probability in Science*. Oxford University Press.

> Foundation of the **linear opinion pool** used in EDP's L4 layer.

**Genest, C. & Zidek, J.V. (1986).** "Combining Probability Distributions: A
Critique and an Annotated Bibliography." *Statistical Science*, 1(1), 114-135.

DOI: [10.1214/ss/1177013825](https://doi.org/10.1214/ss/1177013825)

> Foundation of the **log-odds opinion pool** used in EDP's L4 layer. EDP uses
> a hybrid (α-weighted) combination of linear and log-odds pools.

---

## 2025–2026 Frontier Methods (L7 & Enhancements)

### Conformal Prediction & Adaptive Conformal Inference (ACI)

**Gibbs, I. & Candès, E. (2021).** "Adaptive Conformal Inference Under
Distribution Shift." arXiv:2106.00170.

> **ACI is proposed here.** Gradient-descent-style update of the prediction-set
> width, with coverage guarantees under non-exchangeable / distribution-shift
> settings. EDP's L7 layer implements ACI.

**Zaffran, M., Féron, O., Goude, Y., Josse, J. & Dieuleveut, A. (2022).**
"Adaptive Conformal Predictions for Time Series." *Proceedings of the 39th
International Conference on Machine Learning (ICML 2022)*, PMLR 162:25834-25866.

> Extends ACI to time series with general dependence structure, and proposes
> **AgACI** — an aggregation-based, parameter-free variant. EDP's L7 layer
> implements both ACI and AgACI modes.

---

### Online Bayesian Stacking (Soft-Bayes)

**Waxman, D., Llorente, F. & Djurić, P.M. (2025).** "Bayesian Ensembling:
Insights from Online Optimization and Empirical Bayes." arXiv:2505.15638.

> Proposes **Online Bayesian Stacking (OBS)**: log-score-optimal online
> combination of Bayesian models, with a regret bound. Soft-Bayes appears as a
> portfolio-selection algorithm within OBS. EDP's L2 layer adds OBS as a fourth
> online-aggregation algorithm alongside ML-Poly / EWA / Ridge.

---

### Model Diversity (DTVW)

**Luo, X., Kang, Y. & Luo, X. (2025).** "Bayesian Forecast Combination with
Predictive Priors via Particle Filtering." arXiv:2508.07136.

> Proposes **DTVW (diversity-driven time-varying weights)**: embeds model
> diversity as a forward-looking prior signal in the weight update, penalizing
> redundancy and rewarding informative contributions. EDP's L4 layer implements
> a DTVW-style diversity / effective-source-count metric.

---

### Proper Scoring Rules (Hyvärinen Score)

**Hyvärinen, A. (2005).** "Estimation of Non-Normalized Statistical Models by
Score Matching." *Journal of Machine Learning Research*, 6, 695-709.

> Origin of the **Hyvärinen score** — a proper scoring rule that does not
> require the normalizing constant of the predictive density. EDP's L6 layer
> implements Hyvärinen scoring alongside Brier, Log, and CRPS.

**Ehm, W. & Gneiting, T. (2012).** "Local Proper Scoring Rules of Order Two."
*The Annals of Statistics*, 40(1), 609-637.

DOI: [10.1214/12-AOS973](https://doi.org/10.1214/12-AOS973)

> Systematic characterization of second-order local proper scoring rules
> (including the Hyvärinen score as a special case), providing the theoretical
> underpinning for EDP's L6 calibration layer.

---

## Information Aggregation Theory (Background)

### Prediction Markets as Probability Aggregators

**Wolfers, J. & Zitzewitz, E. (2006).** "Interpreting Prediction Market Prices
as Probabilities." *NBER Working Paper* No. 12200.

DOI: [10.3386/w12200](https://doi.org/10.3386/w12200)

> Demonstrates that prediction-market prices can be interpreted as event
> probabilities — the conceptual basis for treating quoted state-contingent
> prices as probability signals (used in EDP's L1 Shin normalization). Cited
> as *information-aggregation theory*, not as a participation guide.

---

### The Use of Knowledge in Society

**Hayek, F.A. (1945).** "The Use of Knowledge in Society." *American Economic
Review*, 35(4), 519-530.

> Nobel-prize-winning essay on how dispersed information is aggregated through
> price systems — the economic foundation for interpreting price/quote
> movements as information aggregation.

---

## Additional Reading

### Sports Analytics (forecasting literature)

- **Goddard, J. & Asimakopoulos, I. (2004).** "Forecasting football results and
  the efficiency of fixed-odds betting." *Journal of Forecasting*, 23(1), 51-66.

- **Leitner, C., Zeileis, A. & Hornik, K. (2010).** "Forecasting sports
  tournaments by ratings of (prob)abilities: A comparison for the EURO 2008."
  *International Journal of Forecasting*, 26(3), 471-481.

### Risk & Uncertainty

- **Taleb, N.N. (2007).** *The Black Swan: The Impact of the Highly Improbable*.
  Random House.

- **Kahneman, D. & Tversky, A. (1979).** "Prospect Theory: An Analysis of
  Decision under Risk." *Econometrica*, 47(2), 263-291.
  DOI: [10.2307/1914185](https://doi.org/10.2307/1914185)

---

## Citation

If you use EDP in academic work, please cite it as described in
[`CITATION.cff`](../../CITATION.cff) (GitHub renders an APA/BibTeX export from
that file). A BibTeX entry is also provided below:

```bibtex
@software{edp2026,
  author = {{EDP Team}},
  title  = {{EDP: Expectation Domain Perception Method -- A Universal
              Domain-Aware Probabilistic Situation Awareness Framework}},
  year   = {2026},
  version = {2.0.0},
  url    = {https://github.com/ai-nurmamat/EDP},
  license = {MIT}
}
```

---

*EDP stands on the shoulders of giants. We are grateful to all researchers whose
work made this possible. EDP is for academic research and education only.*
