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

  @id:docs.documentation.docs-theme.002 @rule:documentation.docs-theme.shared-accent-palette @inferred @source:docs/stylesheets/extra.css#:root
  Scenario: The splash page and the docs share one accent palette
    Given the accent pair is cyan #22d3ee and indigo #6366f1
    When a reader moves from the splash page to the rendered docs
    Then the splash page heading and button gradients blend cyan into indigo
    And the docs hero heading and primary buttons blend the same cyan into the same indigo
    And the docs theme's primary colour is the indigo accent

  @id:docs.documentation.docs-theme.003 @rule:documentation.docs-theme.legible-links-per-scheme @inferred @source:docs/stylesheets/extra.css#[data-md-color-scheme="slate"]
  Scenario Outline: Links stay legible in both light and dark schemes
    Given the reader has chosen the <scheme> colour scheme
    When the reader views a docs page with links
    Then the page background is <background>
    And links are shown in <link_colour>

    Examples:
      | scheme | background         | link_colour    |
      | light  | white              | indigo #6366f1 |
      | dark   | near-black #0b0f1a | cyan #22d3ee   |

  @id:docs.documentation.docs-theme.004 @rule:documentation.docs-theme.no-stand-in-logo @inferred @source:docs/stylesheets/extra.css#.md-header__button.md-logo
  Scenario: No generic stand-in logo is shown as the brand
    Given the project has no logo configured
    When the reader views the docs header and navigation
    Then no logo icon is shown in the header
    And no logo icon is shown in the navigation title
