@domain:documentation @area:docs-theme @from:stylesheets/extra
Feature: Styling the documentation site and splash page
  Gives readers of the toil-audit docs and splash page one consistent, legible, privacy-respecting look that works offline.

  Background:
    Given the toil-audit documentation site and splash page are published

  @id:docs.documentation.docs-theme.001 @rule:documentation.docs-theme.no-network-loaded-assets @inferred @source:docs/stylesheets/extra.css#:root
  Scenario: The docs theme loads no fonts or assets over the network
    Given a reader opens the documentation
    When the reader's browser renders a docs page
    Then body text uses the operating system's own sans-serif font stack
    And code uses the operating system's own monospace font stack
    And no web font, CDN asset or analytics script is requested by the theme

  @id:docs.documentation.docs-theme.004 @rule:documentation.docs-theme.no-stand-in-logo @inferred @source:docs/stylesheets/extra.css#.md-header__button.md-logo
  Scenario: No generic stand-in logo is shown as the brand
    Given the project has no logo configured
    When the reader views the docs header and navigation
    Then no logo icon is shown in the header
    And no logo icon is shown in the navigation title
