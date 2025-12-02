"""
Black-Scholes Option Pricing Model.

Implements European option pricing using the Black-Scholes-Merton formula.
Includes calculation of:
- Option prices (call and put)
- Greeks (delta, gamma, theta, vega, rho)
- Implied volatility (using Brent's method)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from scipy.stats import norm
from scipy.optimize import brentq

from config.logging import get_logger

logger = get_logger(__name__)


class OptionType(Enum):
    """Option type enumeration."""
    CALL = "call"
    PUT = "put"


@dataclass
class OptionParams:
    """
    Parameters for Black-Scholes option pricing.

    Attributes:
        S: Current stock price (spot price)
        K: Strike price
        T: Time to expiration in years
        r: Risk-free interest rate (annualized, decimal)
        sigma: Volatility (annualized, decimal)
        q: Dividend yield (annualized, decimal, default 0)
    """
    S: float      # Spot price
    K: float      # Strike price
    T: float      # Time to expiration (years)
    r: float      # Risk-free rate
    sigma: float  # Volatility
    q: float = 0.0  # Dividend yield

    def validate(self) -> None:
        """Validate option parameters."""
        if self.S <= 0:
            raise ValueError(f"Spot price must be positive: {self.S}")
        if self.K <= 0:
            raise ValueError(f"Strike price must be positive: {self.K}")
        if self.T <= 0:
            raise ValueError(f"Time to expiration must be positive: {self.T}")
        if self.sigma <= 0:
            raise ValueError(f"Volatility must be positive: {self.sigma}")
        if self.r < 0:
            raise ValueError(f"Risk-free rate cannot be negative: {self.r}")


@dataclass
class OptionResult:
    """
    Result of Black-Scholes calculation.

    Contains price and all Greeks for an option.
    """
    price: float
    delta: float
    gamma: float
    theta: float  # Per day (divide annual by 365)
    vega: float   # Per 1% move in volatility
    rho: float    # Per 1% move in interest rate
    option_type: OptionType
    params: OptionParams


class BlackScholes:
    """
    Black-Scholes-Merton option pricing model.

    Supports European options with continuous dividend yield.

    Usage:
        bs = BlackScholes()

        # Price a call option
        result = bs.calculate(
            S=100,     # Stock price
            K=105,     # Strike
            T=0.5,     # 6 months
            r=0.05,    # 5% risk-free rate
            sigma=0.2, # 20% volatility
            option_type=OptionType.CALL
        )
        print(f"Price: ${result.price:.2f}")
        print(f"Delta: {result.delta:.4f}")

        # Calculate implied volatility
        iv = bs.implied_volatility(
            market_price=5.50,
            S=100, K=105, T=0.5, r=0.05,
            option_type=OptionType.CALL
        )
    """

    @staticmethod
    def _d1(S: float, K: float, T: float, r: float, sigma: float, q: float = 0) -> float:
        """Calculate d1 parameter."""
        return (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

    @staticmethod
    def _d2(d1: float, sigma: float, T: float) -> float:
        """Calculate d2 parameter."""
        return d1 - sigma * math.sqrt(T)

    def call_price(self, params: OptionParams) -> float:
        """
        Calculate European call option price.

        Args:
            params: Option parameters

        Returns:
            Call option price
        """
        params.validate()

        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)
        d2 = self._d2(d1, params.sigma, params.T)

        price = (
            params.S * math.exp(-params.q * params.T) * norm.cdf(d1) -
            params.K * math.exp(-params.r * params.T) * norm.cdf(d2)
        )

        return price

    def put_price(self, params: OptionParams) -> float:
        """
        Calculate European put option price.

        Args:
            params: Option parameters

        Returns:
            Put option price
        """
        params.validate()

        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)
        d2 = self._d2(d1, params.sigma, params.T)

        price = (
            params.K * math.exp(-params.r * params.T) * norm.cdf(-d2) -
            params.S * math.exp(-params.q * params.T) * norm.cdf(-d1)
        )

        return price

    def delta(self, params: OptionParams, option_type: OptionType) -> float:
        """
        Calculate option delta.

        Delta measures the rate of change of option price with respect to
        the underlying asset price.

        Args:
            params: Option parameters
            option_type: CALL or PUT

        Returns:
            Delta (between -1 and 1)
        """
        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)
        discount = math.exp(-params.q * params.T)

        if option_type == OptionType.CALL:
            return discount * norm.cdf(d1)
        else:
            return discount * (norm.cdf(d1) - 1)

    def gamma(self, params: OptionParams) -> float:
        """
        Calculate option gamma.

        Gamma measures the rate of change of delta with respect to
        the underlying asset price. Same for calls and puts.

        Args:
            params: Option parameters

        Returns:
            Gamma (always positive)
        """
        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)
        discount = math.exp(-params.q * params.T)

        return discount * norm.pdf(d1) / (params.S * params.sigma * math.sqrt(params.T))

    def theta(self, params: OptionParams, option_type: OptionType) -> float:
        """
        Calculate option theta (daily).

        Theta measures the rate of change of option price with respect to
        time (time decay). Returns daily theta (annual / 365).

        Args:
            params: Option parameters
            option_type: CALL or PUT

        Returns:
            Theta (usually negative, per day)
        """
        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)
        d2 = self._d2(d1, params.sigma, params.T)

        # First term (same for calls and puts)
        first_term = -(
            params.S * math.exp(-params.q * params.T) * norm.pdf(d1) * params.sigma /
            (2 * math.sqrt(params.T))
        )

        if option_type == OptionType.CALL:
            second_term = -params.r * params.K * math.exp(-params.r * params.T) * norm.cdf(d2)
            third_term = params.q * params.S * math.exp(-params.q * params.T) * norm.cdf(d1)
        else:
            second_term = params.r * params.K * math.exp(-params.r * params.T) * norm.cdf(-d2)
            third_term = -params.q * params.S * math.exp(-params.q * params.T) * norm.cdf(-d1)

        annual_theta = first_term + second_term + third_term

        # Return daily theta
        return annual_theta / 365

    def vega(self, params: OptionParams) -> float:
        """
        Calculate option vega.

        Vega measures the rate of change of option price with respect to
        volatility. Returns vega per 1% change in volatility.
        Same for calls and puts.

        Args:
            params: Option parameters

        Returns:
            Vega (per 1% vol change)
        """
        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)

        # Raw vega (per 100% vol change)
        raw_vega = (
            params.S * math.exp(-params.q * params.T) *
            norm.pdf(d1) * math.sqrt(params.T)
        )

        # Return per 1% change
        return raw_vega / 100

    def rho(self, params: OptionParams, option_type: OptionType) -> float:
        """
        Calculate option rho.

        Rho measures the rate of change of option price with respect to
        the risk-free interest rate. Returns rho per 1% change in rate.

        Args:
            params: Option parameters
            option_type: CALL or PUT

        Returns:
            Rho (per 1% rate change)
        """
        d1 = self._d1(params.S, params.K, params.T, params.r, params.sigma, params.q)
        d2 = self._d2(d1, params.sigma, params.T)

        if option_type == OptionType.CALL:
            raw_rho = (
                params.K * params.T * math.exp(-params.r * params.T) * norm.cdf(d2)
            )
        else:
            raw_rho = (
                -params.K * params.T * math.exp(-params.r * params.T) * norm.cdf(-d2)
            )

        # Return per 1% change
        return raw_rho / 100

    def calculate(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0
    ) -> OptionResult:
        """
        Calculate full option pricing with all Greeks.

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: CALL or PUT
            q: Dividend yield (default 0)

        Returns:
            OptionResult with price and all Greeks
        """
        params = OptionParams(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
        params.validate()

        if option_type == OptionType.CALL:
            price = self.call_price(params)
        else:
            price = self.put_price(params)

        return OptionResult(
            price=price,
            delta=self.delta(params, option_type),
            gamma=self.gamma(params),
            theta=self.theta(params, option_type),
            vega=self.vega(params),
            rho=self.rho(params, option_type),
            option_type=option_type,
            params=params
        )

    def implied_volatility(
        self,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType,
        q: float = 0.0,
        tol: float = 1e-6,
        max_iter: int = 100
    ) -> Optional[float]:
        """
        Calculate implied volatility using Brent's method.

        Finds the volatility that makes the Black-Scholes price equal to
        the market price.

        Args:
            market_price: Observed market price
            S: Spot price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            option_type: CALL or PUT
            q: Dividend yield
            tol: Tolerance for convergence
            max_iter: Maximum iterations

        Returns:
            Implied volatility, or None if not found
        """
        if market_price <= 0:
            logger.warning("Market price must be positive for IV calculation")
            return None

        # Intrinsic value check
        if option_type == OptionType.CALL:
            intrinsic = max(0, S * math.exp(-q * T) - K * math.exp(-r * T))
        else:
            intrinsic = max(0, K * math.exp(-r * T) - S * math.exp(-q * T))

        if market_price < intrinsic - tol:
            logger.warning(
                f"Market price {market_price:.4f} below intrinsic {intrinsic:.4f}"
            )
            return None

        def price_diff(sigma: float) -> float:
            """Difference between model and market price."""
            params = OptionParams(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
            if option_type == OptionType.CALL:
                model_price = self.call_price(params)
            else:
                model_price = self.put_price(params)
            return model_price - market_price

        try:
            # Search between 0.01% and 500% volatility
            iv = brentq(price_diff, 0.0001, 5.0, xtol=tol, maxiter=max_iter)
            return iv
        except ValueError as e:
            logger.warning(f"IV calculation failed: {e}")
            return None
        except RuntimeError as e:
            logger.warning(f"IV calculation did not converge: {e}")
            return None

    def put_call_parity_check(
        self,
        call_price: float,
        put_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float = 0.0,
        tolerance: float = 0.01
    ) -> Tuple[bool, float]:
        """
        Check put-call parity: C - P = S*exp(-qT) - K*exp(-rT)

        Args:
            call_price: Market call price
            put_price: Market put price
            S, K, T, r, q: Option parameters
            tolerance: Acceptable deviation

        Returns:
            Tuple of (is_valid, deviation)
        """
        lhs = call_price - put_price
        rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
        deviation = abs(lhs - rhs)

        return deviation <= tolerance, deviation
