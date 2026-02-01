"""
Trend Service
=============

Macro-level trend analysis and regime segmentation.
Algorithms:
1. PELT (Pruned Exact Linear Time): Exact change point detection.
2. HMM (Hidden Markov Model): Probabilistic regime classification (Bull/Bear/Shock).
3. Bottom-Up PLR (Piecewise Linear Representation): Geometric trend line fitting.
"""

import numpy as np
import pandas as pd
import ruptures as rpt
from hmmlearn import hmm
from typing import List, Dict, Any, Optional


class TrendService:
    def __init__(self):
        pass

    def analyze_trend(self, df: pd.DataFrame, method: str = "all") -> Dict[str, Any]:
        """
        Analyze trend using specified method(s).

        Args:
            df: DataFrame containing 'close' and 'date'.
            method: 'pelt', 'hmm', 'plr', or 'all'.

        Returns:
            Dictionary with results for requested method(s).
        """
        results = {}

        # Ensure data is clean
        if df.empty:
            return results

        prices = df["close"].values
        dates = df["date"].astype(str).str[:10].tolist()  # Ensure string dates

        if method in ["pelt", "all"]:
            results["pelt"] = self._detect_pelt(prices, dates)

        if method in ["hmm", "all"]:
            results["hmm"] = self._detect_hmm(df)

        if method in ["plr", "all"]:
            results["plr"] = self._detect_bottom_up_plr(prices, dates)

        return results

    # ==========================================
    # 1. PELT (Pruned Exact Linear Time)
    # ==========================================
    def _detect_pelt(
        self, prices: np.ndarray, dates: List[str], penalty: float = 10.0
    ) -> List[Dict]:
        """
        Detect change points using PELT algorithm.
        Detects changes in mean and variance.
        """
        # Calculate log-returns or use price directly?
        # Usually PELT on log-returns detects volatility changes.
        # PELT on raw prices detects mean shifts.
        # algo.md suggests cost function based on variance, so let's use signal with changing variance.

        # Normalize prices for better numerical stability with L2 cost
        signal = prices.reshape(-1, 1)

        # Detect change points
        # model="rbf" is robust for general changes. "l2" is standard for mean shift.
        # algo.md mentions mean=0, variance changes.
        algo = rpt.Pelt(model="rbf").fit(signal)
        bkps = algo.predict(pen=penalty)

        segments = []
        start_idx = 0
        for end_idx in bkps:
            # raptures returns end index as exclusive, but we might want inclusive for display
            # Adjust to be valid index
            real_end_idx = min(end_idx, len(prices)) - 1
            if real_end_idx < start_idx:
                continue

            seg_prices = prices[start_idx : real_end_idx + 1]
            avg_price = float(np.mean(seg_prices))
            slope = (
                (seg_prices[-1] - seg_prices[0]) / len(seg_prices)
                if len(seg_prices) > 1
                else 0
            )

            segments.append(
                {
                    "method": "pelt",
                    "startDate": dates[start_idx],
                    "endDate": dates[real_end_idx],
                    "startPrice": float(prices[start_idx]),
                    "endPrice": float(prices[real_end_idx]),
                    "avgPrice": avg_price,
                    "direction": "up" if slope > 0 else "down",
                }
            )
            start_idx = end_idx

        return segments

    # ==========================================
    # 2. HMM (Hidden Markov Model)
    # ==========================================
    def _detect_hmm(self, df: pd.DataFrame, n_components: int = 3) -> List[Dict]:
        """
        Classify market regimes using Gaussian HMM.
        States: Usually corresponding to Bull, Bear, Sideways.
        """
        # Prepare features: Returns and Volatility
        df_copy = df.copy()
        df_copy["returns"] = df_copy["close"].pct_change().fillna(0)
        df_copy["volatility"] = df_copy["returns"].rolling(window=10).std().fillna(0)

        # Observation sequence
        X = df_copy[["returns", "volatility"]].values

        # Add small noise to prevent singular covariance if data is too clean/flat
        X += np.random.normal(0, 1e-6, X.shape)

        # Fit HMM
        # n_components=3 (Bull, Bear, Shock/Sideways)
        # min_covar: Floor on the diagonal of the covariance matrix to prevent overfitting.
        model = hmm.GaussianHMM(
            n_components=n_components,
            covariance_type="full",
            n_iter=200,
            random_state=42,
            min_covar=1e-4,
        )
        try:
            model.fit(X)
            hidden_states = model.predict(X)
        except Exception as e:
            print(f"⚠️ HMM Fit failed: {e}")
            print(f"   Using simple threshold-based fallback classification")

            # Fallback: Simple threshold-based bull/bear/sideways classification
            # This ensures we always return meaningful segments even when HMM fails
            hidden_states = np.zeros(len(X), dtype=int)

            # Classify based on returns: positive -> bull(2), negative -> bear(0), near-zero -> sideways(1)
            returns = X[:, 0]  # First column is returns
            for i, ret in enumerate(returns):
                if ret > 0.01:  # Threshold for bull
                    hidden_states[i] = 2
                elif ret < -0.01:  # Threshold for bear
                    hidden_states[i] = 0
                else:  # Sideways
                    hidden_states[i] = 1

        # Determine which state corresponds to what based on means/variances
        # We assume:
        # High Return, Low Vol -> Bull
        # Negative Return, High Vol -> Bear
        # Low Return, Low Vol -> Sideways
        state_stats = {}
        for i in range(n_components):
            mask = hidden_states == i
            mean_ret = np.mean(X[mask, 0])
            mean_vol = np.mean(X[mask, 1])
            state_stats[i] = {"mean_ret": mean_ret, "mean_vol": mean_vol}

        # Heuristic labeling
        sorted_states = sorted(
            state_stats.items(), key=lambda item: item[1]["mean_ret"]
        )
        # Lowest return (likely negative) -> Bear
        bear_state = sorted_states[0][0]
        # Highest return -> Bull
        bull_state = sorted_states[-1][0]
        # Middle -> Sideways
        sideways_state = sorted_states[1][0] if n_components > 2 else -1

        labels = {bear_state: "Bear", bull_state: "Bull", sideways_state: "Sideways"}

        # Merge consecutive states into segments
        dates = df["date"].astype(str).str[:10].tolist()
        prices = df["close"].values

        segments = []
        if len(hidden_states) == 0:
            return segments

        current_state = hidden_states[0]
        start_idx = 0

        for i in range(1, len(hidden_states)):
            if hidden_states[i] != current_state:
                # End of a segment
                segments.append(
                    {
                        "method": "hmm",
                        "startDate": dates[start_idx],
                        "endDate": dates[i - 1],
                        "type": labels.get(current_state, "Unknown"),
                        "avgPrice": float(np.mean(prices[start_idx:i])),
                        "startPrice": float(prices[start_idx]),  # Add for consistency
                        "endPrice": float(prices[i - 1]),  # Add for consistency
                    }
                )
                current_state = hidden_states[i]
                start_idx = i

        # Last segment
        segments.append(
            {
                "method": "hmm",
                "startDate": dates[start_idx],
                "endDate": dates[-1],
                "type": labels.get(current_state, "Unknown"),
                "avgPrice": float(np.mean(prices[start_idx:])),
                "startPrice": float(prices[start_idx]),  # Add for consistency
                "endPrice": float(prices[-1]),  # Add for consistency
            }
        )

        return segments

    # ==========================================
    # 3. Bottom-Up PLR (Piecewise Linear Reg)
    # ==========================================
    def _detect_bottom_up_plr(
        self, prices: np.ndarray, dates: List[str], max_error: float = 0.05
    ) -> List[Dict]:
        """
        Bottom-Up Piecewise Linear Representation.
        Merges adjacent segments with lowest error cost.
        """
        n = len(prices)
        if n < 2:
            return []

        # Initial segments: create segments between every pair of points
        # This is n/2 segments. For simplicity, we start with n-1 segments (every adjacent pair connects)
        # Represents lines: (0,1), (2,3) ... or (0,1), (1,2), (2,3) continuous?
        # Standard Bottom-Up algorithm usually starts with n/2 finite segments.
        # Let's initialize with T-1 segments connecting (i, i+1).

        class Segment:
            def __init__(self, start, end):
                self.start = start
                self.end = end
                self.error = self._calculate_error()

            def _calculate_error(self):
                # Regression error of points strictly inside the segment from the line connecting start and end
                if self.end - self.start <= 1:
                    return 0.0

                # Equation of line y = ax + b passing through (start, p[start]) and (end, p[end])
                # We normalize x to start at 0 for numeric stability
                y0 = prices[self.start]
                y1 = prices[self.end]
                dx = self.end - self.start
                dy = y1 - y0
                slope = dy / dx
                intercept = y0

                # Predicted y for x in [0, dx]
                x_vals = np.arange(self.end - self.start + 1)
                y_pred = slope * x_vals + intercept
                y_true = prices[self.start : self.end + 1]

                # SSR (Sum Squared Residuals)
                ssr = np.sum((y_true - y_pred) ** 2)
                return ssr

        segments = []
        for i in range(0, n - 1, 2):  # Start with disjoint segments of length 2?
            # Traditional Bottom-Up merges *adjacent* segments.
            # Let's effectively start with segments [0,1], [2,3]...
            # But we want continuous trend lines.
            # A cleaner way for PLR on time series: Start with fine-grained approximation, usually n/2 segments.
            end = min(i + 1, n - 1)
            segments.append(Segment(i, end))

        # Because we skipped points (0-1, 2-3 means 1-2 gap?), we need a linked list structure essentially.
        # Ideally, we partition 0 to N.
        # Let's use a simpler "Iterative Merge" approach on a set of cut points.
        # Initial cut points: 0, 1, 2, ..., n-1.
        cuts = list(range(n))  # All points are cuts initially

        # Cost to remove cut i (merging segment [i-1, i] and [i, i+1] into [i-1, i+1])
        # We calculate the error of the new segment [prev, next] vs sum of old errors (which are 0 initially)

        def calculate_merge_cost(idx_in_cuts):
            # Merging segment left of cuts[idx] and right of cuts[idx]
            # cuts[idx] is the point being removed.
            # New segment would be from cuts[idx-1] to cuts[idx+1]
            start = cuts[idx_in_cuts - 1]
            end = cuts[idx_in_cuts + 1]

            # Create temp segment to calc error
            seg = Segment(start, end)
            return seg.error

        # Greedily remove points until specific condition met
        # Condition: Max error per segment < threshold * total_variation?
        # Or number of segments?
        # algo.md mentions "Max Error Threshold".

        # We normalize prices for error calculation context
        price_range = np.max(prices) - np.min(prices)
        if price_range == 0:
            price_range = 1

        # Scale max_error relative to price range * length?
        # Let's perform iterations until we hit a target number of segments (e.g., 20)
        # OR error exceeds threshold.
        # For visualization, usually 10-20 segments is good for 6 months data.
        target_segments = 15

        while len(cuts) > target_segments:
            best_cost = float("inf")
            best_idx = -1

            # Find best point to remove (cheapest merge)
            # Cannot remove 0 or last point
            for i in range(1, len(cuts) - 1):
                cost = calculate_merge_cost(i)
                if cost < best_cost:
                    best_cost = cost
                    best_idx = i

            # Check stopping condition on error
            # Convert SSR to something interpretable, e.g., RMSE
            # If RMSE of matching is too high, stop.
            # Here we just use target_segments count for simplicity/visual stability unless error explodes.

            if best_idx != -1:
                cuts.pop(best_idx)
            else:
                break

        # Construct final result
        res_segments = []
        for i in range(len(cuts) - 1):
            start = cuts[i]
            end = cuts[i + 1]
            # seg_prices = prices[start : end + 1] # Unused

            res_segments.append(
                {
                    "method": "plr",
                    "startDate": dates[start],
                    "endDate": dates[end],
                    "startPrice": float(prices[start]),
                    "endPrice": float(prices[end]),
                    "direction": "up" if prices[end] > prices[start] else "down",
                }
            )

        return res_segments

    def process_semantic_regimes(
        self, raw_segments: List[Dict], min_duration_days: int = 7
    ) -> List[Dict]:
        """
        Post-process raw segments to create Semantic Regimes.
        1. Smoothing: Merge short noise segments ("Sandwich" noise).
        2. Merging: Combine contiguous segments of the same type.
        """
        if not raw_segments:
            return []

        # deep copy to avoid mutating original
        import copy
        from datetime import datetime

        segments = copy.deepcopy(raw_segments)

        # Helper: Calculate duration
        def get_duration(seg):
            d1 = datetime.strptime(seg["startDate"], "%Y-%m-%d")
            d2 = datetime.strptime(seg["endDate"], "%Y-%m-%d")
            return (d2 - d1).days

        # Helper: Normalize type
        def get_type(seg):
            return seg.get("type") or seg.get("direction") or "sideways"

        # 1. Smoothing (Sandwich Logic)
        # Iterate and flip short segments that are sandwiched between same-type segments
        # Multiple passes usually not needed for simple noise removal, 1 pass is enough
        for i in range(1, len(segments) - 1):
            prev = segments[i - 1]
            curr = segments[i]
            next_seg = segments[i + 1]

            prev_type = get_type(prev)
            curr_type = get_type(curr)
            next_type = get_type(next_seg)

            if prev_type == next_type and curr_type != prev_type:
                duration = get_duration(curr)
                if duration < min_duration_days:
                    # Flip current to match neighbors
                    # We just change direction/type logic.
                    # We accept that 'price' might be non-linear, but for Semantic Regime
                    # we care about the "Phase Classification".
                    curr["direction"] = prev.get("direction")
                    curr["type"] = prev.get("type")

        # 2. Merging Contiguous Segments
        merged_segments = []
        if not segments:
            return []

        # Initialize first merged segment with events list
        current_merge = segments[0]
        current_merge["events"] = [copy.deepcopy(segments[0])]

        for i in range(1, len(segments)):
            next_seg = segments[i]
            curr_type = get_type(current_merge)
            next_type = get_type(next_seg)

            if curr_type == next_type:
                # Merge
                current_merge["endDate"] = next_seg["endDate"]
                current_merge["endPrice"] = next_seg["endPrice"]
                # Append to events
                current_merge["events"].append(copy.deepcopy(next_seg))
            else:
                # Commit current and start new
                merged_segments.append(current_merge)
                current_merge = next_seg
                current_merge["events"] = [copy.deepcopy(next_seg)]

        merged_segments.append(current_merge)

        # Add metadata indicating it's a semantic regime
        for seg in merged_segments:
            seg["zone_type"] = "semantic_regime"
            # Calculate return for the whole merged segment
            try:
                start_p = float(seg["startPrice"])
                end_p = float(seg["endPrice"])
                ret = (end_p - start_p) / start_p if start_p != 0 else 0
                seg["avg_return"] = ret
                seg["summary"] = f"{get_type(seg).title()} ({ret * 100:.1f}%)"
            except:
                pass

        return merged_segments
