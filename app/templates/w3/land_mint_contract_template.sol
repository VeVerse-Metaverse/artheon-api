// SPDX-License-Identifier: MPL-2.0

pragma solidity 0.8.10;

import "@openzeppelin/contracts/utils/Strings.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

/**
 * @title <%= @erc721.name %>
 * <@&737394570425401357> <%= @erc721.description |> String.replace(~r/[\r\n]+/, " ") %>
 */
contract <%= @erc721.contract_name %> is ERC721, Ownable, Pausable {
    using Strings for uint256;

    uint256 public constant MAX_ID = <%= @erc721.total_supply %>;
    uint256 public price = <%= @erc721.minting_price %>;

    /**
     * <@&737394570425401357> Setup NFT.
     */
    constructor() ERC721("<%= @erc721.name %>", "<%= @erc721.symbol %>") {
        _pause();
    }

    // <%= if @erc721.minting_coin_address === GreetGenerators.NFT.ERC721.zero_address() %>
    /**
     * <@&737394570425401357> Mint NFT for a gas coin fee.
     *
     * @param _tokenId NFTs id
     */
    function mint(uint256 _tokenId) external payable whenNotPaused {
        require(_tokenId <= MAX_ID, "no token to mint");
        if (price > 0) {
            require(price == msg.value, "invalid price");
        }

        // solhint-disable avoid-low-level-calls
        (bool _succeed,) = payable(owner()).call{value: msg.value}("");
        require(_succeed, "failed to pay");

        _mint(_msgSender(), _tokenId);
    }

    /**
     * <@&737394570425401357> Set price for NFT in _gasCoinAmount by owner.
     *
     * @param _maxBatchId type of NFT to mint
     * @param _gasCoinAmount price in gas coin for minting
     * @param _maxMintableTokenId regulates current minting phase, set 0 to stop
     */
    function setMintingRules(uint256 _gasCoinAmount) external onlyOwner {
        require(_gasCoinAmount >= 0, "overflow of price");
        price = _gasCoinAmount;
    }
    // <% end %>

    /**
     * <@&737394570425401357> enables owner to pause / unpause minting.
     *
     * @param _paused true to pause, false to continue
     */
    function setPaused(bool _paused) external onlyOwner {
        if (_paused) _pause();
        else _unpause();
    }

    /**
     * <@&737394570425401357> API URL prefix.
     *
     * @param _tokenId specific token to render.
     * @return API URL prifix with metadata, token id will be attached by `tokenURI` automatically.
     */
    function _baseURI() public pure override returns (string memory) {
        return "<%= @erc721.token_uri %>";
    }
}