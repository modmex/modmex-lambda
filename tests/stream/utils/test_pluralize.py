from expects import equal, expect
from modmex_lambda.stream.utils.pluralize import pluralize


def test_pluralize():
    expect(pluralize('box')).to(equal('boxes'))
    expect(pluralize('buzz')).to(equal('buzzes'))
    expect(pluralize('brush')).to(equal('brushes'))
    expect(pluralize('party')).to(equal('parties'))
    expect(pluralize('thing')).to(equal('things'))
