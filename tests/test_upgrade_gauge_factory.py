from brownie import (
    accounts,
    interface,
    Controller,
    SettV3,
    MyStrategy,
    ERC20Upgradeable,
    Contract
)
import brownie
from config import (
    BADGER_DEV_MULTISIG,
    WANT,
    LP_COMPONENT,
    REWARD_TOKEN,
    PROTECTED_TOKENS,
    FEES,
)
from helpers.SnapshotManager import SnapshotManager

from dotmap import DotMap
import pytest


"""
Tests for the Upgrade from mainnet version to upgraded version
These tests must be run on arbitrum-fork
"""

NEW_GAUGE = "0xDB3fd1bfC67b5D4325cb31C04E0Cae52f1787FD6"
NEW_GAUGE_FACTORY = "0xabC000d88f23Bb45525E447528DBF656A9D55bf5"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@pytest.fixture
def vault_proxy():
    return SettV3.at("0xBA418CDdd91111F5c1D1Ac2777Fa8CEa28D71843")

@pytest.fixture
def controller_proxy(vault_proxy):
    return Controller.at(vault_proxy.controller())

@pytest.fixture
def strat_proxy():
    return MyStrategy.at("0x4C5d19Da5EaeC298B79879a5f7481bEDE055F4F8")

@pytest.fixture
def proxy_admin():
    """
     Verify by doing web3.eth.getStorageAt("0x4C5d19Da5EaeC298B79879a5f7481bEDE055F4F8", int(
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
    )).hex()
    """
    return Contract.from_explorer("0x95713d825BcAA799A8e2F2b6c75aeD8b89124852")


@pytest.fixture
def proxy_admin_gov():
    """
        Also found at proxy_admin.owner()
    """
    return accounts.at("0xb364bAb258ad35dd83c7dd4E8AC78676b7aa1e9F", force=True)

def test_upgrade_and_harvest(vault_proxy, controller_proxy, deployer, strat_proxy, proxy_admin, proxy_admin_gov):
    new_strat_logic = MyStrategy.deploy({"from": deployer})
    
    with brownie.reverts():
        strat_proxy.gaugeFactory()

    ## Setting all variables, we'll use them later
    prev_strategist = strat_proxy.strategist()
    prev_controller = strat_proxy.controller()
    prev_gov = strat_proxy.governance()
    prev_guardian = strat_proxy.guardian()
    prev_keeper = strat_proxy.keeper()
    prev_perFeeG = strat_proxy.performanceFeeGovernance()
    prev_perFeeS = strat_proxy.performanceFeeStrategist()
    prev_reward = strat_proxy.reward()
    prev_unit = strat_proxy.uniswap()
    prev_gauge = strat_proxy.gauge()
    prev_swapr_router = strat_proxy.SWAPR_ROUTER()

    gov = accounts.at(strat_proxy.governance(), force=True)
    
    # Deploy new logic
    proxy_admin.upgrade(strat_proxy, new_strat_logic, {"from": proxy_admin_gov})
    # Set new gauge
    strat_proxy.setGauge(NEW_GAUGE, {"from": gov})
    strat_proxy.setGaugeFactory(NEW_GAUGE_FACTORY, {"from": gov})

    assert strat_proxy.gauge() == NEW_GAUGE
    assert strat_proxy.gaugeFactory() == NEW_GAUGE_FACTORY

    gauge = interface.ICurveGauge(NEW_GAUGE)
    
    want = interface.IERC20(WANT)
    prev_bal = gauge.balanceOf(strat_proxy.address)

    brownie.chain.sleep(60*60*24)
    brownie.chain.mine()

    snap = SnapshotManager(vault_proxy, strat_proxy, controller_proxy, "StrategySnapshot")
    # Will confirm full harvest functionality
    snap.settHarvest({"from": gov})

    after_bal = gauge.balanceOf(strat_proxy.address)

    assert after_bal > prev_bal

    ## Checking all variables are as expected
    assert prev_strategist == strat_proxy.strategist()
    assert prev_controller == strat_proxy.controller()
    assert prev_gov == strat_proxy.governance()
    assert prev_guardian == strat_proxy.guardian()
    assert prev_keeper == strat_proxy.keeper()
    assert prev_perFeeG == strat_proxy.performanceFeeGovernance()
    assert prev_perFeeS == strat_proxy.performanceFeeStrategist()
    assert prev_reward == strat_proxy.reward()
    assert prev_unit == strat_proxy.uniswap()
    assert prev_swapr_router == strat_proxy.SWAPR_ROUTER()
    assert NEW_GAUGE == strat_proxy.gauge()
    assert NEW_GAUGE_FACTORY == strat_proxy.gaugeFactory()

    ## Also run all ordinary operation just because
    strat_proxy.tend({"from": gov})
    controller_proxy.withdrawAll(vault_proxy.token(), {"from": gov})
    vault_proxy.earn({"from": gov})
    
