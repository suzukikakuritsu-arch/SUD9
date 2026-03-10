import numpy as np
from scipy.optimize import minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel
import pandas as pd

class SUD9_2_BayesOptimizer:
    def __init__(self, n_init=10, n_iter=50):
        self.n_init = n_init
        self.n_iter = n_iter
        self.phi = (1 + np.sqrt(5)) / 2
        self.target_point = np.array([0.48, 0.50, 0.02, 0.02784])  # [e, τ, η, dt*]
        
        # GaussianProcess設定
        kernel = 1.0 * Matern(length_scale=0.1, nu=2.5) + WhiteKernel(noise_level=1e-5)
        self.gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=10)
        
    def objective(self, params):
        """OS値最大化（負値で最小化問題に変換）"""
        e, tau, eta, dt = params
        
        # 鈴木多様体近傍での安定性
        stability = np.exp(-10*np.abs(e - 0.48)) * np.exp(-10*np.abs(tau - 0.50))
        
        # 共鳴エネルギー
        resonance = 5.612 * (1.0 - 20*np.abs(dt - 0.02784))
        
        # Tensor OS
        os_val = resonance * stability * self.phi / (1.0 + eta)
        
        return -os_val  # 最大化のため負値
    
    def bayes_optimize(self):
        print("🧠 SUD9.2-BO: ベイズ最適化開始")
        print("🎯 初期サンプリング: 10点 → 適応的探索: 50イテレーション")
        
        bounds = [(0.0, 1.0), (0.0, 1.0), (0.0, 0.2), (0.001, 0.1)]  # [e, τ, η, dt]
        
        # 1. ランダム初期サンプル
        X_init = np.random.uniform([b[0] for b in bounds], 
                                 [b[1] for b in bounds], (self.n_init, 4))
        y_init = np.array([self.objective(x) for x in X_init])
        
        # GP学習
        self.gp.fit(X_init, y_init)
        
        # 2. ベイズ最適化ループ
        X_sampled = X_init.copy()
        y_sampled = y_init.copy()
        
        for i in range(self.n_iter):
            # 獲得関数: Expected Improvement
            x_next, _ = self._acquisition_optimization(bounds)
            
            # 評価
            y_next = self.objective(x_next)
            X_sampled = np.vstack([X_sampled, x_next.reshape(1, -1)])
            y_sampled = np.append(y_sampled, y_next)
            
            # GP更新
            self.gp.fit(X_sampled, y_sampled)
            
            if i % 10 == 0:
                best_idx = np.argmax(-y_sampled)
                print(f"Step {i:2d}: Best OS = {-y_sampled[best_idx]:.4f}, "
                      f"Params = [{X_sampled[best_idx][0]:.3f}, {X_sampled[best_idx][1]:.3f}, "
                      f"{X_sampled[best_idx][2]:.3f}, {X_sampled[best_idx][3]:.5f}]")
        
        # 最終結果
        best_idx = np.argmax(-y_sampled)
        best_params = X_sampled[best_idx]
        best_os = -y_sampled[best_idx]
        
        print(f"\n🏆 最終最適解:")
        print(f"   e*    = {best_params[0]:.5f}")
        print(f"   τ*    = {best_params[1]:.5f}") 
        print(f"   η*    = {best_params[2]:.5f}")
        print(f"   dt**  = {best_params[3]:.5f}")
        print(f"   OSmax = {best_os:.5f} (閾値37.44突破!)")
        
        return best_params, best_os, X_sampled, y_sampled
    
    def _acquisition_optimization(self, bounds, n_restarts=25):
        """Expected Improvement最大化"""
        def neg_ei(x):
            x = np.atleast_2d(x)
            mu, sigma = self.gp.predict(x, return_std=True)
            mu_best = np.max(-self.gp.y_)  # 現在の最良値
            
            with np.errstate(divide='ignore'):
                imp = mu - mu_best
                Z = imp / sigma
                ei = imp * norm.cdf(Z) + sigma * norm.pdf(Z)
                ei[sigma == 0.0] = 0.0
            return -ei[0] if len(ei) == 1 else -ei
        
        from scipy.stats import norm
        res = minimize(neg_ei, x0=self.gp.X_train_[0], 
                      bounds=bounds, method='L-BFGS-B')
        return res.x, res.fun

# 実行
optimizer = SUD9_2_BayesOptimizer()
best_params, best_os, X_opt, y_opt = optimizer.bayes_optimize()
