"""Extra maps for baseq3: what they are, where they come from and how to get them.

Most of them come from lvlworld.com, which hands out every download behind a
short-lived token. ArenaHub asks for one the way the site's download page does,
and falls back to the copy kept in this repository's assets/maps.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import net
from .context import Context, TaskError

LVLWORLD = "https://lvlworld.com"
BACKUP = "https://raw.githubusercontent.com/Evilchuck666/ArenaHub/main/assets/maps"
"""Where the copies in assets/maps are served from."""

GAME_DIR = "baseq3"
"""Maps go into baseq3, so every mod can load them."""


@dataclass(frozen=True)
class LvlWorld:
    """A lvlworld.com release whose download holds the exact map pack."""

    id: int
    sha256: str
    """Checksum of the release's ZIP archive."""


@dataclass(frozen=True)
class MapPack:
    filename: str
    """The .pk3 file in baseq3."""
    title: str
    author: str
    maps: tuple[str, ...]
    """Map names to use with /map, as found in the .pk3."""
    modes: tuple[str, ...]
    sha256: str
    size: int
    lvlworld: LvlWorld | None = None
    page: str = ""
    """Web page about the map, when it is not the lvlworld release."""

    @property
    def url(self) -> str:
        if self.page:
            return self.page
        assert self.lvlworld is not None
        return f"{LVLWORLD}/review/id:{self.lvlworld.id}"

    @property
    def backup_url(self) -> str:
        return f"{BACKUP}/{self.filename}"


MAPS: tuple[MapPack, ...] = (
    MapPack(
        filename="atrocity.pk3",
        title="Atrocity Exhibition",
        author="Decker & DruZli",
        maps=("atrocity",),
        modes=("ffa", "tourney"),
        sha256="c7a184f7a034084ead31658dbd0a5ebe94c190169a9f6f444be04b31daa6635d",
        size=675887,
        lvlworld=LvlWorld(2424, "d3ce898446aec0b621dff2c71f01120be5abfd7d62f5da64a56bb1c0668f8b4d"),
    ),
    MapPack(
        filename="auh3dm1.pk3",
        title="OverWhelming Hostility",
        author="Auhsan",
        maps=("auh3dm1",),
        modes=("ffa", "tourney"),
        sha256="c70a1e0e1e908f288697a83fd23599cfe291387f54ae4c3e0386f74fd9cdffef",
        size=2890989,
        page="https://lvlworld.com/review/id:614",
    ),
    MapPack(
        filename="bubctf1.pk3",
        title="The Vast and Furious",
        author="ButterB",
        maps=("bubctf1",),
        modes=("ctf",),
        sha256="7dafd7754b844f3db620b51eecb057eb2463ceaa21928df020f9b05705346b24",
        size=4417675,
        lvlworld=LvlWorld(1279, "691b4d4b354c021df247b9fffb87dd304790768fbaa14b52db7aee372fc28bc2"),
    ),
    MapPack(
        filename="chiropteraDM.pk3",
        title="ChiropteraDM",
        author="Alcatraz, nunuk & Sock",
        maps=("chiropteradm",),
        modes=("ffa", "tourney"),
        sha256="f935a5dfcab23beccd46b1a5c6b8027310826400f8f51397229ca4662a9729b8",
        size=4626599,
        lvlworld=LvlWorld(1243, "f0f1d2391d85549e9b16320a1a8cca47031103b2478e873415c85c796e4b353a"),
    ),
    MapPack(
        filename="ct3ctf2.pk3",
        title="Fluorescent",
        author="cityy",
        maps=("ct3ctf2",),
        modes=("ctf",),
        sha256="abdde7afb9a2e54054ebc26b733719fb2110458c3e2c935fc8bf7e6c4f401dc5",
        size=17027842,
        lvlworld=LvlWorld(2184, "81f9bd1413e5d00932bd1ce5627f31d6f55082145570cb6bd9e2e956e82e275e"),
    ),
    MapPack(
        filename="ct3dm4.pk3",
        title="Paranoid",
        author="cityy",
        maps=("ct3dm4",),
        modes=("ffa", "tourney", "team"),
        sha256="6ef13e0adc316caa604eba0a897205142f1ff9faa11110364efdb6594bbee0ed",
        size=12319157,
        lvlworld=LvlWorld(2098, "af0049e89c0380093a06c3821f66461de3305217bc614450874cb6b7f2957815"),
    ),
    MapPack(
        filename="ct3dm5.pk3",
        title="Left Behind",
        author="cityy",
        maps=("ct3dm5",),
        modes=("ffa", "tourney", "team"),
        sha256="b7ec0b8d67475b9bb898cfcc143d292c84a1b57d94fadc2a2d779d2f5269ac55",
        size=13106112,
        lvlworld=LvlWorld(2121, "56caad880e5b6a8d477dfce7680616541109a13773aa980f72a54c8f9ee69370"),
    ),
    MapPack(
        filename="ct3tourney2.pk3",
        title="Rainy Day",
        author="cityy",
        maps=("ct3tourney2", "pro-ct3tourney2"),
        modes=("ffa", "tourney"),
        sha256="8e8c26d583dd7518f9b8616bd18eb5cb167372f85c3798ce996bcd0b349fd5bc",
        size=14179986,
        lvlworld=LvlWorld(2100, "80e4e0be76d2b92099378a2760c88626deeb4655f4eaa29e30d20b4d438838e8"),
    ),
    MapPack(
        filename="d3xf1.pk3",
        title="Up Close and Personal",
        author="DruZli",
        maps=("d3xf1",),
        modes=("tourney",),
        sha256="8eacde8ead749ef8751180d03c4e59506b29faf0c9e5d76211987ceba7cd11db",
        size=916993,
        lvlworld=LvlWorld(663, "c053464fd70f7dbca222ac455e7fed0bd843dd05ffda61657d441855e290f41d"),
    ),
    MapPack(
        filename="dboxctf2.pk3",
        title="Crossed Paths",
        author="Drunken Boxer",
        maps=("dboxctf2",),
        modes=("ctf",),
        sha256="bb76a14af614150aab266e52734f583b6fc7646c8d7575ad4a44abca13cca118",
        size=2198531,
        lvlworld=LvlWorld(567, "f699b1b386287aef55e1fed74e0daab4875cc213a4bf3bdb023799432f174a2d"),
    ),
    MapPack(
        filename="dc-mappack.pk3",
        title="Dreamcast Maps",
        author="Various",
        maps=(
            "dc_map02",
            "dc_map03",
            "dc_map04",
            "dc_map05",
            "dc_map06",
            "dc_map07",
            "dc_map08",
            "dc_map09",
            "dc_map10",
            "dc_map11",
            "dc_map12",
            "dc_map13",
            "dc_map14",
            "dc_map15",
            "dc_map16",
            "dc_map17",
            "dc_map18",
            "dc_map19",
            "dc_map20",
            "dc_map21",
            "dc_map22",
            "dc_map23",
            "dc_map24",
        ),
        modes=(),
        sha256="95cdfb3007a8349f02ed2cd7ff7b66a573bbea2f6bf821d7ccf562bd99f8e533",
        size=52192697,
        page="https://lvlworld.com/review/id:999",
    ),
    MapPack(
        filename="focal_p132.pk3",
        title="Focal Point",
        author="Sock",
        maps=("focal_p132",),
        modes=("ffa", "tourney", "team"),
        sha256="ffa6e75cb2e879a479169da63dd170a1615a932d0e2925ff537ae2ee7df27a2e",
        size=8422010,
        lvlworld=LvlWorld(2084, "21f520779205ad04836a089c9a34944c48d25b9e55eb7c9d32389872eaf110dc"),
    ),
    MapPack(
        filename="hub3aeroq3.pk3",
        title="Aerowalk",
        author="the Hubster",
        maps=("hub3aeroq3",),
        modes=("tourney",),
        sha256="c1b8dd7b4c41e6703751a0c2c88a594319bbf71b52ca861bcfd18f5e18078ca1",
        size=1251417,
        lvlworld=LvlWorld(836, "5b7ba89734c6abb90dd12ff5c5dca491c98bce3b6169f1858426e18ebbcac671"),
    ),
    MapPack(
        filename="hub3aeroq3a.pk3",
        title="Aerowalk [Hubster's Remix II]",
        author="the Hubster",
        maps=("hub3aeroq3a",),
        modes=("tourney",),
        sha256="5722452cace17eac05e8c7ef81cdcbcadee1d3a033699efada8ba8c91895447c",
        size=3067690,
        lvlworld=LvlWorld(1717, "2c40289ac7ed5ca7300edee2b9251a1a9d810e16338afedccf2458a5e122c9f7"),
    ),
    MapPack(
        filename="hub3dm1.pk3",
        title="Dismemberment",
        author="the Hubster",
        maps=("hub3dm1",),
        modes=("tourney",),
        sha256="bf5dd8ca608f22e6b2730e5d9387ebb3404fa0daa3ba8aaf5e155ba1a78ae0b3",
        size=1736428,
        lvlworld=LvlWorld(822, "5861b5c515502593e5ea6855c5fe31be0d2202c6d08134d90c99d10f1a813c5d"),
    ),
    MapPack(
        filename="japanc.pk3",
        title="Japanese Castles",
        author="g1zm0",
        maps=("japanctf", "japandm"),
        modes=("ffa", "team", "ctf"),
        sha256="fb512936b824414c033f84a2f7338ec9f0a7d2cbb05fd3eeebcaf8a993c6697d",
        size=4429465,
        lvlworld=LvlWorld(44, "d148c41d705bc7e23e7d6fcd7ba5b8557e2e42b2691ecaf63d0c9c2ee583e8db"),
    ),
    MapPack(
        filename="jstrq3dm1.pk3",
        title="Danse Macabre",
        author="Jester",
        maps=("jstrq3dm1",),
        modes=("ffa", "tourney"),
        sha256="6471367ecccbe17d6b807ae37fe353dd0bf42ae8649eada081725c747eb3cf72",
        size=1105456,
        lvlworld=LvlWorld(2137, "511dc54464c58827a4caa0150af67aa9033a2b0331cac4f79aa3628e4abbccbe"),
    ),
    MapPack(
        filename="map-13gate_xt.pk3",
        title="Arena Gate CTF - Extended",
        author="sst13",
        maps=("13gate_xt",),
        modes=("ctf",),
        sha256="983c337f5e444df3a75efdf7a2da2c020147a59409f7e55a00e1b19cd651cae3",
        size=1367354,
        lvlworld=LvlWorld(1929, "fcfeafe94a24668a13beee58e696af5578d1bb7e6ba51797a36fe8092458683d"),
    ),
    MapPack(
        filename="map-13vast.pk3",
        title="The Vast And Furious - 13th RMX",
        author="sst13",
        maps=("13vast",),
        modes=("ctf",),
        sha256="4b658870d77370260a45447de3b648e8ccc890b4c6887b54fad6d9ec8abbbcb5",
        size=4098942,
        lvlworld=LvlWorld(1807, "53a72b3a2edcee10fec3ffda02a41f70f1db9b05b40c018e890390a7977d9fe6"),
    ),
    MapPack(
        filename="map-acid3dm9.pk3",
        title="chlorophyl",
        author="blemish, ekse & acid",
        maps=("acid3dm9",),
        modes=("ffa", "tourney", "team"),
        sha256="e5b9e6d56cc991fdef1a17625e0e951ae2264118dc7f97be037449b10ff703a0",
        size=2314410,
        lvlworld=LvlWorld(2038, "d673757337a86fa954a30f25856fba47906606710ffdf79a559662fe555ee8e6"),
    ),
    MapPack(
        filename="map-charonq2dm1v2.pk3",
        title="Return to the Edge",
        author="Charon",
        maps=("charonq2dm1v2",),
        modes=("ffa", "tourney"),
        sha256="9b511a447d0b367c6062e957a9e7899397e51d2b2354e6ecaf1a98decac2db85",
        size=1845252,
        lvlworld=LvlWorld(500, "c5a131257ad851f629db28ff7b941f077ffbcf8c75654dd35c9a45bb5f5f2bfd"),
    ),
    MapPack(
        filename="map_dm-fora_q3duel5.pk3",
        title="The Immortal Coil",
        author="Foralarx",
        maps=("fora_q3duel5",),
        modes=("ffa", "tourney"),
        sha256="b7029fad50c872f2ae457f4b06492478fb3c27222904951b2918aa6e3d9a2166",
        size=4719412,
        lvlworld=LvlWorld(2409, "ca196a4c148596db0e478c569bb109db84feee200573e71e45db7748b6ea1095"),
    ),
    MapPack(
        filename="map_nodm13.pk3",
        title="The Dark Zone",
        author="swelt",
        maps=("nodm13",),
        modes=("ffa", "tourney", "team"),
        sha256="49ad47e9968dd6391c96df3cdca37b966a78874f4a14df0712c081ff1870ac4b",
        size=2710490,
        lvlworld=LvlWorld(2422, "f56be760207ddbc5603f88bca9679e6856df541f32cef783c1c2436dcac6c4e3"),
    ),
    MapPack(
        filename="map_phantq3dm1_rev.pk3",
        title="Battleforged",
        author="Phantazm11",
        maps=("phantq3dm1_rev",),
        modes=("ffa", "tourney"),
        sha256="a66a2f616a695465ef63b31618ddcd301ccae4a3605bca5a90e8a3ab6ab5f988",
        size=1421780,
        lvlworld=LvlWorld(2043, "e487c2df2b28b602cbfe20b28a6940e0f779dd8ebc028071e558af39f916a979"),
    ),
    MapPack(
        filename="mg_final.pk3",
        title="Mystic Gemini",
        author="Sock & Mr.Lake",
        maps=("mg_final",),
        modes=("ctf",),
        sha256="702f35bf52b7a7459e29a2934db11dc847cd81bc9a287112edfd20b2c190e0f9",
        size=16564435,
        lvlworld=LvlWorld(2002, "fb2c1ce60d62c88600e101f1a48260dde50c6ab9339b7318d71a8368e264419d"),
    ),
    MapPack(
        filename="mrcq3t6.pk3",
        title="Bitter Embrace",
        author="Mr.CleaN",
        maps=("mrcq3t6", "mrcq3t6_ffa"),
        modes=("ffa", "tourney"),
        sha256="eefd171ab5d0271512d1277ef9ec8b0543ce73ff2172665647d97e04843bda3c",
        size=3046070,
        lvlworld=LvlWorld(1017, "979972baefe12121b0e71337311ba9bf1fdfc8de6cd31689f1185c19c6111c40"),
    ),
    MapPack(
        filename="n3pak0.pk3",
        title="Temple of Amun & Temple of Amun 2v2",
        author="noctis",
        maps=("n3dm1", "n3tourney1"),
        modes=("ffa", "tourney", "team"),
        sha256="4e5d685f6bd35c693a39fb268cb4f962922d17393974366fd3c6cf05ae65f8d2",
        size=8071529,
        lvlworld=LvlWorld(1964, "0f71f8ccd4d806d498c95f11e7a74b768a96884d54bf0df68e49f7073def0bb5"),
    ),
    MapPack(
        filename="obs3dm7.pk3",
        title="The Killing Machine for Q3A",
        author="Obsessed",
        maps=("obs3dm7",),
        modes=("ffa", "tourney"),
        sha256="a378939ba940c1b00537ab4b740aa322890c0db3876ec7ae8a67dbad007e7d07",
        size=11763812,
        lvlworld=LvlWorld(2372, "ec8f483b7fb7d066859d32c90532b2a07136e398f5e313569afc190f48a7f893"),
    ),
    MapPack(
        filename="OspRa3map1.pk3",
        title="Ra3map1 OSP",
        author="Mortal",
        maps=("ospra3map1",),
        modes=(),
        sha256="e2efb090335a1a77f617e5fc42fef22ee85c4cedee35461c2d9ae9a9dbc7e92e",
        size=2243604,
        lvlworld=LvlWorld(1485, "4ebb7008c8835acb601462fb8daa87c19d4eed9e40ac898c215ef1b8d9f2e34c"),
    ),
    MapPack(
        filename="overkill.pk3",
        title="Overkill!",
        author="Wiebo de Wit",
        maps=("overkill",),
        modes=("ffa", "team"),
        sha256="2b7275f4684c136346c1b887eaec6470d1aa025e188ec3cb7ed813ede8f2b275",
        size=2494904,
        lvlworld=LvlWorld(80, "06bd85cf38842f7476d603e4fe658d9cf9adec5805253eefff12339168cef6f2"),
    ),
    MapPack(
        filename="pak9hqq37.pk3",
        title="High Quality Quake 3.7 (graphics pack)",
        author="ZerTerO",
        maps=("pro-q3tourney7",),
        modes=(),
        sha256="efd53e63aa20499cf0843ac3a6213202d44cca67b0f506fb4049bb27f0865982",
        size=22059012,
        page="https://www.moddb.com/mods/high-quality-quake",
    ),
    MapPack(
        filename="phantq3dm3_rev.pk3",
        title="Corrosion",
        author="Phantazm11",
        maps=("phantq3dm3_rev",),
        modes=("ffa", "team"),
        sha256="e77530e768dfd393c343f53b79e04d568d32d1aa5491105a1b51a77edd6212e0",
        size=15786595,
        lvlworld=LvlWorld(2131, "7a6a0eaae73b16adad8a3c38aa3688f3f89616c0768e540a25b9daab42816141"),
    ),
    MapPack(
        filename="phantq3dm4.pk3",
        title="Windsong Keep",
        author="Phantazm11",
        maps=("phantq3dm4",),
        modes=("ffa", "tourney"),
        sha256="61fc54331968ca9c330fe40c96556abe9b780230ee7f0e379ddee4668ed17986",
        size=12905305,
        lvlworld=LvlWorld(2190, "264b76800c90f2ed0dcc899b1f50a0a73b406fce03b779def3e6adcb96a64e77"),
    ),
    MapPack(
        filename="pro-q3tourney7.pk3",
        title="Almost Lost",
        author="id Software",
        maps=("pro-q3tourney7",),
        modes=("ffa", "tourney", "team"),
        sha256="4f1b3546a7bbdf27e674e70b5c7adf5d07a3549232d377f90ba2cfb2ce1b5878",
        size=1233925,
        lvlworld=LvlWorld(1631, "a7faded8adc2a7011e55e9b38fe667186a254a13f92b9d30b4f27203cfc6da69"),
    ),
    MapPack(
        filename="pukka3tourney2.pk3",
        title="Evolution",
        author="thefury",
        maps=("pukka3tourney2",),
        modes=("ffa", "tourney"),
        sha256="e4b2d8bb9e7e5c199af5f37d4330a7622d30480bb3a15e3ced5c9e98ed61288e",
        size=10332176,
        lvlworld=LvlWorld(1841, "5b3a65f224e2ba136721aab8c0d607bfa3bedd1b360ae9144a48f5bcd8123bbc"),
    ),
    MapPack(
        filename="pukka3tourney6.pk3",
        title="Kamasutra",
        author="thefury",
        maps=("pukka3tourney6",),
        modes=("ffa", "tourney"),
        sha256="1b9e1345e3da8ba31a2bfd2085f0912b9ca7f99c549913272a6a2e279b68ddf5",
        size=14138995,
        lvlworld=LvlWorld(2058, "2cb7fe659091790477a8b12d4061e3614d88e938154a4425674bf33284927a8c"),
    ),
    MapPack(
        filename="q3q1dm4.pk3",
        title="The Bad Place (2)",
        author="Mike Zuber",
        maps=("q3q1dm4",),
        modes=("ffa", "team"),
        sha256="fdccea1e3a823a026a51b8f18094ca5f9038aa6d12a4698121e77a18f78da4fb",
        size=542412,
        lvlworld=LvlWorld(185, "a7071dc67340cbc8a1940ce0ab9140d098cfe4f035061572fdc5ea7e07410bdc"),
    ),
    MapPack(
        filename="Q3shw24.pk3",
        title="The Dreadful Place",
        author="ShadoW",
        maps=("q3shw24",),
        modes=("ffa", "team"),
        sha256="9d4b2940718d98a346a0b51c4ae3cd9930ee3555996460fa93fd617e5da5615a",
        size=11782089,
        lvlworld=LvlWorld(2077, "d517e04c15e3e5fca40bdfb5c4fa96a9c5c75ce92deb1fa544fbe86992137649"),
    ),
    MapPack(
        filename="q3shw26.pk3",
        title="Battlegrounds",
        author="ShadoW",
        maps=("q3shw26",),
        modes=("ffa", "tourney", "team"),
        sha256="c45ec9cf33132e3267c3a742720d9d2673ca09f98915cf0bdd0c55288e9effef",
        size=11777525,
        lvlworld=LvlWorld(2120, "420b12d8cf6f34b3605fa054fc6c29ac541a046bf856b5cf7dfb3279a870fc2c"),
    ),
    MapPack(
        filename="qxtourney1.pk3",
        title="Gothic Rage",
        author="Quaker-X",
        maps=("qxtourney1",),
        modes=("ffa", "tourney"),
        sha256="c0ff9a884a9c0185d12b7e7d49677ad53317eadce127fa28589d7ead1595ee45",
        size=1129199,
        lvlworld=LvlWorld(784, "0a2326cf7b8e69e7c005e630d4e156e0eb276662d14488f66d515c999996dc0f"),
    ),
    MapPack(
        filename="sokar3dm5.pk3",
        title="Ice Storm",
        author="SoKaR",
        maps=("sokar3dm5",),
        modes=("ffa", "tourney"),
        sha256="37ca5c689e487d0ec8ad66dd49c28ccf00c4fe0a3c8123a05bf4e13859a38422",
        size=5645519,
        lvlworld=LvlWorld(1671, "77c58486ef19780bc33c8bf24ea895a122207ef863dbd2a33bbc672a9a293c02"),
    ),
    MapPack(
        filename="solitude.pk3",
        title="Solitude",
        author="Hipshot",
        maps=("solitude",),
        modes=("tourney",),
        sha256="8b99dc0567b0991ac470ce845f072baff17fbd90da4e1e3d1fee782f08055fca",
        size=17789650,
        lvlworld=LvlWorld(2126, "944bfc0ea14160c2085e6ddbbc0ea3f33a52ad1fe0e80d84aeb95c2668815c73"),
    ),
    MapPack(
        filename="storm3tourney8.pk3",
        title="Devilish",
        author="StormShadow",
        maps=("storm3tourney8",),
        modes=("ffa", "tourney", "team"),
        sha256="ccd4b7b2cf14109aea526fab798ade39be1d760add13451e68e3c06c5d198882",
        size=5202864,
        lvlworld=LvlWorld(2160, "40dc913f5d42c191ed7411d69c70cc01d8ccf269e2afc9f3f8aed6cf010a6e59"),
    ),
    MapPack(
        filename="tfa3dm1.pk3",
        title="Ambush!",
        author="acrobat",
        maps=("tfa3dm1",),
        modes=("ffa", "team"),
        sha256="1928a9b6d3628ba4407613f03b845ac2eed506aefa32cc69b05556e796e4b3ba",
        size=8636027,
        lvlworld=LvlWorld(2421, "437c92388848baa2433d01422d2d42e45caecc2b209624503c122ab65336fbe0"),
    ),
    MapPack(
        filename="trespass.pk3",
        title="Trespass",
        author="Pat Howard",
        maps=("trespass",),
        modes=("ffa", "tourney", "team"),
        sha256="17c1bd04d770e8bbddad20bf007e44bb5d4cc496d1c8c9c752c067dc024d8a07",
        size=27221244,
        lvlworld=LvlWorld(2323, "88718d74f6c276274bcefa1634c29eac80a8572e5667c462b6ed0ecfb6a87cba"),
    ),
    MapPack(
        filename="ztn3dm2.pk3",
        title="Beatbox",
        author="ztn",
        maps=("ztn3dm2",),
        modes=("ffa", "tourney"),
        sha256="63bdc051c742fbc58b8a886d9678b39823e4258b9055ad19c5242adcc3f14df8",
        size=875548,
        lvlworld=LvlWorld(107, "c359eb9b9b5acd7a57df876d081f6a39bb82a823baa54fb45b8428b1056d7764"),
    ),
    MapPack(
        filename="ztn3tourney1.pk3",
        title="Blood Run Tourney",
        author="ztn",
        maps=("ztn3tourney1",),
        modes=("tourney",),
        sha256="01aa1c8db8d5be058f7ae3acb50514c723a4859638cbc910f78d906990a04c83",
        size=887986,
        lvlworld=LvlWorld(800, "c8a2d186a286e9d95f87066e438a4e5247eaa5810879ca7b2fab2d2a44a55364"),
    ),
)


@dataclass
class InstallResult:
    added: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    """One message per map pack that could not be downloaded."""


def install(ctx: Context, install_dir: Path, downloads: Path) -> InstallResult:
    """Put every map pack into baseq3; packs already there and intact are kept.

    A map pack that cannot be downloaded is reported, not fatal: the games work without it.
    """
    result = InstallResult()
    for index, pack in enumerate(MAPS):
        ctx.check()
        ctx.progress(index / len(MAPS), pack.title)
        dest = install_dir / GAME_DIR / pack.filename
        if dest.is_file() and net.sha256_of(dest) == pack.sha256:
            continue
        try:
            _fetch(ctx, pack, dest, downloads)
        except TaskError as exc:
            result.failed.append(f"{pack.title} ({pack.filename}): {exc}")
            continue
        result.added.append(dest)
    return result


def _fetch(ctx: Context, pack: MapPack, dest: Path, downloads: Path) -> None:
    if pack.lvlworld:
        try:
            url = lvlworld_url(pack.lvlworld.id)
            archive = downloads / f"lvlworld-{pack.lvlworld.id}.zip"
            net.fetch(ctx, (url,), archive, pack.lvlworld.sha256, f"{pack.title} (lvlworld)")
            _extract_pack(archive, pack, dest)
            return
        except (requests.RequestException, TaskError, zipfile.BadZipFile) as exc:
            ctx.log(f"lvlworld.com did not work for {pack.filename} ({exc}); using the backup copy")
    net.fetch(ctx, (pack.backup_url,), dest, pack.sha256, pack.filename)


def lvlworld_url(release_id: int) -> str:
    """Ask lvlworld.com for a download token, like its download page does."""
    page_url = f"{LVLWORLD}/download/id:{release_id}"
    with net.session() as s:
        response = s.get(page_url, timeout=net.TIMEOUT)
        response.raise_for_status()
        tokens = re.search(r'tk:\["(\w+)","(\w+)"\]', response.text)
        name = re.search(r'f\.append\("z","([^"]+)"\)', response.text)
        if not tokens or not name:
            raise TaskError("the download page has changed")

        form = {"z": name[1], "s": tokens[1], "h": tokens[2], "d": "lvl"}
        response = s.post(
            f"{LVLWORLD}/dload", data=form, headers={"Referer": page_url}, timeout=net.TIMEOUT
        )
        response.raise_for_status()
        try:
            r = response.json()
            if not r.get("success"):
                raise TaskError("no download token was given")
            return f"{r['l']}/{r['p']}/{r['z']}?{r['t']}"
        except (ValueError, KeyError, AttributeError) as exc:
            raise TaskError(f"unexpected token reply: {exc}") from exc


def _extract_pack(archive: Path, pack: MapPack, dest: Path) -> None:
    """Copy the map pack out of a release archive, checking that it is the pinned one."""
    with zipfile.ZipFile(archive) as zf:
        members = [
            m
            for m in zf.infolist()
            if m.filename.replace("\\", "/").rsplit("/", 1)[-1].lower() == pack.filename.lower()
        ]
        if not members:
            raise TaskError(f"{archive.name} has no {pack.filename}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".part")
        with zf.open(members[0]) as src, partial.open("wb") as out:
            shutil.copyfileobj(src, out)
    if net.sha256_of(partial) != pack.sha256:
        partial.unlink()
        raise TaskError(f"the {pack.filename} in {archive.name} is a different version")
    partial.replace(dest)
