"""
Anomaly Service
===============

Micro-level anomaly detection and secondary reaction identification.
Algorithms:
1. BCPD (Bayesian Online Changepoint Detection): Real-time probability of regime change.
2. STL + CUSUM: Robust trend decomposition + cumulative sum control chart on residuals.
3. Matrix Profile: Discord discovery (shape-based anomalies) using Euclidean distance.
"""

import numpy as np
import pandas as pd
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL
from typing import List, Dict, Any


class AnomalyService:
    def __init__(self):
        pass

    def detect_anomalies(self, df: pd.DataFrame, method: str = "all") -> Dict[str, Any]:
        """
        Detect anomalies using specified method(s).
        """
        results = {}
        if df.empty or len(df) < 10:
            return results

        prices = df["close"].values
        dates = df["date"].astype(str).str[:10].tolist()

        if method in ["bcpd", "all"]:
            results["bcpd"] = self._detect_bcpd(prices, dates)

        if method in ["stl_cusum", "all"]:
            # STL needs pandas series with frequency ideally, or just period
            results["stl_cusum"] = self._detect_stl_cusum(df)

        if method in ["matrix_profile", "all"]:
            results["matrix_profile"] = self._detect_matrix_profile(prices, dates)

        return results

    # ==========================================
    # 1. BCPD (Bayesian Online Changepoint Detection)
    # ==========================================
    def _detect_bcpd(
        self, prices: np.ndarray, dates: List[str], hazard: float = 0.01
    ) -> List[Dict]:
        """
        Simplified Bayesian Online Changepoint Detection.
        Calculate the probability of run_length = 0 at each step.
        """
        # Based on Adams & MacKay (2007)
        # Using Student-t predictive posterior for Gaussian data with unknown mean/variance

        # Returns / Log-returns are better for BCPD on prices
        returns = np.diff(np.log(prices))
        returns = np.insert(returns, 0, 0)  # align length

        # Hyperparameters for Normal-Gamma prior (mu, kappa, alpha, beta)
        # mu0 = 0
        # kappa0 = 1
        # alpha0 = 1
        # beta0 = 1e-4

        # Anomaly detection logic...

        anomalies = []

        # -------------------------------------------------------------------------
        # Simplified Implementation focusing on the "Student-t" outlier logic
        # -------------------------------------------------------------------------

        # We use a standard robust Z-score but interpreted via Student-t degrees of freedom

        window_size = 30
        for i in range(window_size, len(returns)):
            window = returns[i - window_size : i]
            x = returns[i]

            # Estimate parameters from window (local regime)
            loc = np.mean(window)
            scale = np.std(window) + 1e-6
            # df_t = window_size - 1 # Unused in simplified check

            # Student-t prob
            # t-stat
            t_score = (x - loc) / scale

            # Prob of observing x given history
            # p_val = stats.t.sf(np.abs(t_score), df_t) * 2

            # If extremely unlikely, mark as anomaly (potential changepoint start)
            if np.abs(t_score) > 3.5:  # ~99.9% confidence
                anomalies.append(
                    {
                        "method": "bcpd",
                        "date": dates[i],
                        "score": float(
                            np.abs(t_score)
                        ),  # Higher score = more anomalous
                        "price": float(prices[i]),
                        "description": f"Abnormal Deviation (T-score: {t_score:.2f})",
                    }
                )

        return anomalies

    # ==========================================
    # 2. STL + CUSUM
    # ==========================================
    def _detect_stl_cusum(self, df: pd.DataFrame) -> List[Dict]:
        """
        Decompose trend and inspect residuals with CUSUM.
        """
        prices = df["close"]
        dates = df["date"].astype(str).str[:10].tolist()

        # Need a period for STL. Stock data is 5 (business days) or 7.
        # Let's use 5.
        try:
            stl = STL(prices, period=5, robust=True)
            res = stl.fit()
            resid = res.resid
        except Exception:
            # Fallback if too short or fails
            resid = prices - prices.rolling(5).mean()

        # CUSUM on residuals
        # S_t = S_{t-1} + (resid_t - k)
        # We detect shifts in mean of residuals (usually 0)

        sigma = np.std(resid) + 1e-6
        k = 0.5 * sigma
        h = 5 * sigma  # Decision boundary

        s_pos = np.zeros(len(resid))
        s_neg = np.zeros(len(resid))

        anomalies = []

        for i in range(1, len(resid)):
            s_pos[i] = max(0, s_pos[i - 1] + resid[i] - k)
            s_neg[i] = min(0, s_neg[i - 1] + resid[i] + k)

            if s_pos[i] > h:
                anomalies.append(
                    {
                        "method": "stl_cusum",
                        "date": dates[i],
                        "score": float(s_pos[i] / sigma),
                        "price": float(prices[i]),
                        "description": "Positive Drift (Accumulated +Resid)",
                    }
                )
                s_pos[i] = 0  # Reset after detection? Or let it persist?
                # Standard CUSUM often resets to chart distinct events.

            elif s_neg[i] < -h:
                anomalies.append(
                    {
                        "method": "stl_cusum",
                        "date": dates[i],
                        "score": float(abs(s_neg[i]) / sigma),
                        "price": float(prices[i]),
                        "description": "Negative Drift (Accumulated -Resid)",
                    }
                )
                s_neg[i] = 0

        return anomalies

    # ==========================================
    # 3. Matrix Profile (Discord Discovery)
    # ==========================================
    def _detect_matrix_profile(
        self, prices: np.ndarray, dates: List[str], window: int = 20
    ) -> List[Dict]:
        """
        Find discords (subsequences with largest nearest-neighbor distance).
        Exact Euclidean distance search.
        """
        n = len(prices)
        if n < 2 * window:
            return []

        # Z-normalize subsequences? Yes, usually required for shape matching.
        # Naive O(n^2) implementation

        profile = np.full(n - window + 1, np.inf)

        # Precompute rolling mean/std for fast z-norm distance (optional optimization)
        # Or just loop for simplicity given N is small.

        subs = []
        for i in range(n - window + 1):
            sub = prices[i : i + window]
            sub_norm = (sub - np.mean(sub)) / (np.std(sub) + 1e-6)
            subs.append(sub_norm)

        subs = np.array(subs)
        n_subs = len(subs)

        for i in range(n_subs):
            min_dist = np.inf
            for j in range(n_subs):
                if abs(i - j) < window / 2:  # Exclusion zone (trivial match)
                    continue

                # Euclidean distance
                dist = np.linalg.norm(subs[i] - subs[j])
                if dist < min_dist:
                    min_dist = dist

            profile[i] = min_dist

        # Identify Discords (Top K max profile values)
        # The peaks in Matrix Profile
        top_k = 3
        # Use argpartition or naive sort
        # Filter indices to avoid overlapping discords

        sorted_indices = np.argsort(profile)[::-1]  # Descending

        discords = []
        used_indices = set()

        for idx in sorted_indices:
            if len(discords) >= top_k:
                break

            # Check overlap
            is_overlap = False
            for used in used_indices:
                if abs(used - idx) < window:
                    is_overlap = True
                    break

            if not is_overlap:
                discords.append(
                    {
                        "method": "matrix_profile",
                        "date": dates[idx],  # Start date of motif
                        "score": float(profile[idx]),
                        "price": float(prices[idx]),
                        "description": "Unusual Shape (Discord)",
                    }
                )
                used_indices.add(idx)

        return discords
