import polars as pl
import statsmodels.formula.api as smf
import pylahman

Teams = pl.from_pandas(pylahman.Teams())
_teams_rename = {"2B": "X2B", "3B": "X3B", "IPOuts": "IPouts"}
Teams = Teams.rename({k: v for k, v in _teams_rename.items() if k in Teams.columns})
PREDICTORS = [
    "logRS", "logRA", "H", "X2B", "X3B", "HR", "BB", "SO", "CS",
    "HBP", "SF", "ERA", "CG", "SHO", "IPouts", "HA", "HRA", "BBA",
    "SOA", "E", "DP", "FP", "SV",
]
df = (
    Teams.filter((pl.col("yearID") >= 2010) & (pl.col("yearID") <= 2025) & (pl.col("yearID") != 2020))
    .with_columns([
        (pl.col("W") / (pl.col("W") + pl.col("L"))).alias("WPct"),
        pl.col("R").log().alias("logRS"),
        pl.col("RA").log().alias("logRA"),
    ])
    .select(["WPct", "W", "L"] + PREDICTORS)
    .drop_nulls()
    .to_pandas()
)

def _fit_glm(data, target, features, family, weights=None):
    formula = f"{target} ~ 1" if len(features) == 0 else f"{target} ~ {' + '.join(features)}"
    kwargs = {"formula": formula, "data": data, "family": family}
    if weights is not None:
        kwargs["var_weights"] = weights
    return smf.glm(**kwargs).fit()

def _model_aic(model, data, weights=None):
    return -2 * model.llf + 2 * len(model.params)

def stepwise_selection(data, target, predictors, family, weights=None):
    current_predictors = predictors.copy()
    best_model = _fit_glm(data, target, current_predictors, family, weights)
    while True:
        best_aic = _model_aic(best_model, data, weights)
        candidate_model = None
        candidate_predictors = None
        for feature in current_predictors:
            trial_features = [f for f in current_predictors if f != feature]
            model = _fit_glm(data, target, trial_features, family, weights)
            aic = _model_aic(model, data, weights)
            if aic < best_aic:
                best_aic, candidate_model, candidate_predictors = aic, model, trial_features
        for feature in predictors:
            if feature not in current_predictors:
                trial_features = current_predictors + [feature]
                model = _fit_glm(data, target, trial_features, family, weights)
                aic = _model_aic(model, data, weights)
                if aic < best_aic:
                    best_aic, candidate_model, candidate_predictors = aic, model, trial_features
        if candidate_model is None:
            break
        best_model, current_predictors = candidate_model, candidate_predictors
    return best_model, current_predictors

step_m, sel = stepwise_selection(df, "W", PREDICTORS, smf.families.Poisson())
print("selected:", sorted(sel))
print("AIC:", _model_aic(step_m, df))
print("formula:", step_m.model.formula)
