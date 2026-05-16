[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('smoke', 'regression', 'all')]
    [string]$Suite = 'all',

    [string]$Python = 'py -3'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-TestSuite {
    param(
        [Parameter(Mandatory)]
        [string]$Arguments
    )

    Invoke-Expression "$Python -m unittest $Arguments"
}

Push-Location $repoRoot
try {
    switch ($Suite) {
        'smoke' {
            Invoke-TestSuite 'tests/test_raffle_functional.py'
        }
        'regression' {
            Invoke-TestSuite 'tests/test_raffle_commands.py tests/test_postgres.py tests/test_main.py tests/test_utils.py'
        }
        'all' {
            Invoke-TestSuite 'discover -s tests'
        }
    }
}
finally {
    Pop-Location
}
