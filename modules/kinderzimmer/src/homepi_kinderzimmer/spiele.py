"""Der Spielkatalog.

Feste Daten, keine Datenbank: Ein Spiel ist eine Faehigkeit der Firmware, und
die aendert sich mit einem Update, nicht mit einem Klick. Die Website zeigt
genau diese Texte.

Fuer die Texte gilt einfache Sprache. Die Begruendung erzaehlt, was Forscher
beobachtet haben, statt Fachbegriffe aufzuzaehlen. Wer einen Text aendert:
kurze Saetze, ein Gedanke je Satz, Namen der Forscher nennen, damit man
nachlesen kann.

``bereit`` heisst: die Firmware kann das Spiel. Erst dann laesst es sich in den
Einstellungen einschalten.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Phase:
    nummer: int
    titel: str
    alter: str


@dataclass(frozen=True, slots=True)
class Spiel:
    id: str
    nummer: int
    phase: int
    titel: str
    alter: str
    #: Wie es funktioniert
    ablauf: str
    #: Was es foerdert
    foerdert: str
    #: Warum - die Forschung dahinter, so erzaehlt, dass jeder sie versteht
    warum: str
    bereit: bool = False


PHASEN: tuple[Phase, ...] = (
    Phase(1, "Ich bewirke etwas", "5–9 Monate"),
    Phase(2, "Dinge verschwinden nicht", "8–18 Monate"),
    Phase(3, "Ich ordne die Welt", "1½–3 Jahre"),
    Phase(4, "Ich denke mit", "3–6 Jahre"),
)


SPIELE: tuple[Spiel, ...] = (
    Spiel(
        id="licht-und-klang",
        nummer=1,
        phase=1,
        titel="Licht und Klang",
        alter="ab 5 Monaten",
        ablauf=(
            "Drückt sie auf einen großen Knopf, leuchtet ein sanftes Licht und ein kurzer "
            "Klang ertönt. Jeder Knopf hat immer dieselbe Farbe und denselben Klang. "
            "Fangt mit einem Knopf an. Einen zweiten mit anderem Klang gibt es erst, "
            "wenn sie den ersten sicher trifft."
        ),
        foerdert=(
            "Das Gefühl „Ich kann etwas bewirken“. Dazu das gezielte Greifen und Drücken mit "
            "der Hand."
        ),
        warum=(
            "Die Forscherin Carolyn Rovee-Collier band drei Monate alten Babys ein Band ans "
            "Bein. Das Band war mit einem Mobile über ihrem Bett verbunden. Die Babys merkten "
            "schnell, dass ihr Strampeln das Mobile bewegt, und strampelten mehr. Tage später "
            "wussten sie es noch. Babys lernen also sehr früh, dass ihr Handeln etwas auslöst. "
            "Das klappt aber nur, wenn die Wirkung sofort kommt und jedes Mal gleich ist. "
            "Deshalb reagiert das Gerät ohne Verzögerung und immer gleich."
        ),
        bereit=True,
    ),
    Spiel(
        id="stimmen",
        nummer=2,
        phase=1,
        titel="Vertraute Stimmen",
        alter="ab 5 Monaten",
        ablauf=(
            "Ihr legt eine Figur auf das Lesefeld, zum Beispiel die Oma-Figur. Dann hört sie "
            "Omas Stimme: „Hallo, meine Kleine!“ Am Anfang legt ihr die Figur auf, und sie "
            "schaut und hört zu. Etwa ab neun Monaten legt sie die Figur selbst auf."
        ),
        foerdert=(
            "Die Bindung zu vertrauten Menschen, das Wiedererkennen von Stimmen und das Zuhören."
        ),
        warum=(
            "Schon Neugeborene erkennen die Stimme ihrer Mutter. Das zeigten Anthony DeCasper "
            "und William Fifer 1980 mit einem Schnuller, der mit einem Lautsprecher verbunden "
            "war. Saugten die Babys auf eine bestimmte Weise, hörten sie ihre Mutter, sonst "
            "eine fremde Frau. Schon nach wenigen Minuten saugten sie so, dass die Mutter "
            "sprach. Vertraute Stimmen halten die Aufmerksamkeit eines Babys länger als "
            "fremde. Deshalb gibt es hier keine Computerstimme, sondern nur eure Aufnahmen."
        ),
        bereit=True,
    ),
    Spiel(
        id="kuckuck",
        nummer=3,
        phase=2,
        titel="Kuckuck",
        alter="ab 8 Monaten",
        ablauf=(
            "Liegt die Figur auf dem Lesefeld, spielt ein Lied. Nimmt sie die Figur weg, hört "
            "das Lied auf. Legt sie sie zurück, geht es weiter. Später legt ihr ein Tuch über "
            "die Figur. Das Lied spielt weiter, denn die Figur ist ja noch da: „Die Kuh ist "
            "noch da!“"
        ),
        foerdert="Das Verständnis, dass Dinge weiter da sind, auch wenn man sie nicht sieht.",
        warum=(
            "Der Entwicklungsforscher Jean Piaget versteckte vor Babys ein Spielzeug unter "
            "einem Tuch. Jüngere Babys suchten nicht danach, als hätte es aufgehört zu "
            "existieren. Etwa ab acht Monaten hoben sie das Tuch hoch und holten das "
            "Spielzeug. Jetzt haben sie verstanden, dass Dinge nicht einfach verschwinden. "
            "Das ist ein großer Schritt im Denken. Deshalb lieben Kinder in diesem Alter "
            "Kuckuck-Spiele so sehr: Sie üben genau diese neue Entdeckung."
        ),
    ),
    Spiel(
        id="tierlaute",
        nummer=4,
        phase=2,
        titel="Wer macht was?",
        alter="ab 10 Monaten",
        ablauf=(
            "Sie legt eine Tierfigur auf. Zuerst kommt das echte Geräusch des Tieres, dann "
            "eure Stimme: „Die Kuh macht muuh.“ Sprecht es nach, macht eine kleine Pause und "
            "gebt ihr Zeit, selbst einen Laut zu machen."
        ),
        foerdert="Wörter mit Dingen verbinden, erste Wörter und das Abwechseln beim Sprechen.",
        warum=(
            "Babys lernen Sprache von Menschen, nicht von Geräten. Die Forscherin Patricia "
            "Kuhl ließ neun Monate alte amerikanische Babys Chinesisch hören. Eine Gruppe "
            "hörte eine Person im Raum, eine andere dieselbe Person auf Video oder nur als "
            "Ton. Nur von der echten Person lernten die Babys die fremden Laute. Das Gerät "
            "liefert also den Anlass, gelernt wird im Gespräch mit euch. Tierlaute wie „muh“ "
            "gehören oft zu den ersten Wörtern, weil sie leicht nachzumachen sind."
        ),
    ),
    Spiel(
        id="farben",
        nummer=5,
        phase=3,
        titel="Finde etwas Rotes",
        alter="ab 1½ Jahren",
        ablauf=(
            "Das Gerät fragt: „Kannst du mir etwas Rotes geben?“ Jede rote Figur ist richtig. "
            "Legt sie eine andere Farbe auf, sagt es nur: „Das ist blau! Hast du noch etwas "
            "Rotes?“ Ein „falsch“ gibt es nicht. Beginnt mit zwei Farben, die sich stark "
            "unterscheiden, etwa Rot und Blau."
        ),
        foerdert="Dinge nach einer Eigenschaft sortieren und die Namen der Farben.",
        warum=(
            "Babys sehen Farben schon früh. Die Wörter dafür lernen Kinder aber erstaunlich "
            "spät, meist erst mit zweieinhalb bis drei Jahren. Das hat zum Beispiel die "
            "Forscherin Katie Wagner mit Kollegen beobachtet. Vorher verwechseln Kinder die "
            "Farbwörter oft, obwohl sie die Farben genau sehen. Außerdem verstehen Kinder "
            "ein Wort lange bevor sie es selbst sagen. Deshalb fragt das Spiel nach dem "
            "Erkennen („Gib mir …“) und nicht nach dem Benennen („Welche Farbe ist das?“)."
        ),
    ),
    Spiel(
        id="formen",
        nummer=6,
        phase=3,
        titel="Formenbox",
        alter="ab 1½ Jahren",
        ablauf=(
            "Ein Deckel hat Löcher in verschiedenen Formen, und nur die passende Form fällt "
            "hindurch. Darunter liegt das Lesefeld, und das Gerät sagt, welche Form angekommen "
            "ist. Fangt mit dem Kreis an, er passt in jeder Drehung. Danach kommen Quadrat und "
            "Dreieck."
        ),
        foerdert="Räumliches Denken, Formen unterscheiden und das Zusammenspiel von Hand und Auge.",
        warum=(
            "Die schwedischen Forscher Helena Örnkloo und Claes von Hofsten gaben Kindern "
            "eine Formenbox. Mit eineinhalb Jahren drückten die meisten einfach drauflos. "
            "Erst mit gut zwei Jahren drehten viele die Form vorher passend zum Loch. Dafür "
            "muss ein Kind sich die Form im Kopf vorstellen und mit dem Loch vergleichen. Das "
            "ist eine frühe Form von räumlichem Denken. Der Kreis passt in jeder Drehung und "
            "ist deshalb der leichteste Anfang."
        ),
    ),
    Spiel(
        id="rituale",
        nummer=7,
        phase=3,
        titel="Rituale",
        alter="ab 1½ Jahren",
        ablauf=(
            "Bestimmte Figuren gehören zu festen Momenten am Tag. Der Mond spielt das "
            "Schlaflied, und auf Wunsch dimmt Home Assistant dabei das Licht. Die Zahnbürste "
            "spielt ein Lied, das genau zwei Minuten dauert. Zuerst legt ihr die Figur auf, "
            "später macht sie es selbst."
        ),
        foerdert=(
            "Sich im Tagesablauf zurechtfinden, leichtere Übergänge vom Spielen ins Bett und "
            "Selbstständigkeit."
        ),
        warum=(
            "Kleine Kinder können noch keine Uhr lesen. Feste Abläufe sagen ihnen, was als "
            "Nächstes kommt, und das gibt Sicherheit. Die Schlafforscherin Jodi Mindell hat "
            "dazu über zehntausend Familien in vierzehn Ländern befragt. Kinder mit einem "
            "festen Abendritual schliefen schneller ein, wachten nachts seltener auf und "
            "schliefen länger. Je öfter das Ritual stattfand, desto deutlicher war der "
            "Unterschied. Legt sie den Mond selbst auf, ist das Schlafengehen ihre eigene "
            "Handlung und keine Anweisung."
        ),
    ),
    Spiel(
        id="hoerfiguren",
        nummer=8,
        phase=3,
        titel="Hörfiguren",
        alter="ab 2 Jahren",
        ablauf=(
            "Jede Figur spielt ein Lied oder eine Geschichte, zum Beispiel ihr Lieblingsbuch, "
            "von euch vorgelesen. Mit den Knöpfen geht es weiter oder zurück. Die Lautstärke "
            "bleibt immer unter der Grenze, die ihr eingestellt habt."
        ),
        foerdert="Zuhören, Wortschatz und selbst entscheiden, was läuft.",
        warum=(
            "Kinder, denen viel vorgelesen wird, kennen mehr Wörter. Die Forscherin Jessica "
            "Logan hat mit Kollegen ausgerechnet, wie viel das ausmacht. Ein Kind, dem jeden "
            "Tag ein Bilderbuch vorgelesen wird, hat bis zum fünften Geburtstag fast "
            "300.000 Wörter mehr gehört als ein Kind, dem nie vorgelesen wird. In Büchern "
            "stehen viele Wörter, die im Alltag selten vorkommen. Eine Aufnahme ersetzt das "
            "gemeinsame Lesen nicht. Aber sie kann die Geschichte so oft hören, wie sie will, "
            "und durch Wiederholung lernen Kinder Wörter."
        ),
    ),
    Spiel(
        id="mengen",
        nummer=9,
        phase=4,
        titel="Mengen zählen",
        alter="ab 3 Jahren",
        ablauf=(
            "Auf den Figuren sind Punkte wie auf einem Würfel, eins bis fünf. Legt sie eine "
            "auf, zählt das Gerät mit, und bei jeder Zahl leuchtet ein Licht mehr: „Eins, zwei, "
            "drei – drei Punkte!“ Später geht es umgekehrt: „Drück dreimal.“ Jeder Druck gibt "
            "ein Licht und eine Zahl."
        ),
        foerdert=(
            "Kleine Mengen auf einen Blick erkennen, richtig zählen und verstehen, dass die "
            "letzte Zahl sagt, wie viele es sind."
        ),
        warum=(
            "Die Forscher Rochel Gelman und Randy Gallistel haben beschrieben, was Zählen "
            "eigentlich verlangt. Man gibt jedem Ding genau eine Zahl, sagt die Zahlen immer "
            "in derselben Reihenfolge und weiß, dass die letzte Zahl die Menge ist. Viele "
            "Dreijährige können schon bis zehn aufsagen, verstehen das aber noch nicht. "
            "Fragt man „Wie viele sind es?“, zählen sie einfach noch einmal. Bis drei erkennen "
            "dagegen schon kleine Kinder eine Menge auf einen Blick. Deshalb beginnt das "
            "Spiel mit Mengen und lässt Ziffern weg."
        ),
    ),
    Spiel(
        id="echo",
        nummer=10,
        phase=4,
        titel="Echo",
        alter="ab 3 Jahren",
        ablauf=(
            "Das Gerät spielt eine kurze Folge auf den Knöpfen vor, mit Licht und Ton. Sie "
            "drückt die Folge nach. Es beginnt mit einem einzigen Ton. Klappt es, kommt ein Ton "
            "dazu. Klappt es nicht, wird die Folge unauffällig wieder kürzer. Für jüngere "
            "Kinder ist es freies Trommeln: Jeder Knopf ist ein Instrument."
        ),
        foerdert="Sich etwas kurz merken, aufmerksam bleiben und warten, bis man dran ist.",
        warum=(
            "Forscher nennen diese Fähigkeiten „exekutive Funktionen“: sich etwas merken, "
            "einen Impuls bremsen, bei der Sache bleiben. In Neuseeland begleitet eine große "
            "Studie rund tausend Menschen seit ihrer Geburt im Jahr 1972. Die Forscherin "
            "Terrie Moffitt fand dort heraus: Kinder mit mehr Selbstbeherrschung waren als "
            "Erwachsene gesünder und hatten weniger Geldsorgen. Diese Fähigkeiten wachsen "
            "zwischen drei und fünf Jahren besonders stark, und man kann sie üben, am "
            "besten im Spiel."
        ),
    ),
    Spiel(
        id="gefuehle",
        nummer=11,
        phase=4,
        titel="Wie geht's dir?",
        alter="ab 3 Jahren",
        ablauf=(
            "Es gibt Figuren für fröhlich, traurig, wütend und ängstlich. Sie legt die auf, "
            "die zu ihr passt. Das Gerät sagt das Gefühl mit Namen: „Du bist wütend. Das ist "
            "in Ordnung.“ Auf dem Display seht ihr, welche Figur sie gewählt hat. Das ist ein "
            "Anlass, darüber zu reden."
        ),
        foerdert="Gefühle erkennen, benennen und mit ihnen umgehen.",
        warum=(
            "Was man benennen kann, kann man leichter bändigen. Der Hirnforscher Matthew "
            "Lieberman zeigte Erwachsenen Bilder von wütenden oder ängstlichen Gesichtern. "
            "Sagten sie, welches Gefühl sie sahen, beruhigte sich der Teil des Gehirns, der "
            "Alarm schlägt. Bei Kindern zeigt sich Ähnliches. Die Forscherin Susanne Denham "
            "fand: Kindergartenkinder, die Gefühle gut erkennen und benennen, kommen besser "
            "mit anderen Kindern zurecht. Das Gerät gibt das Wort, das Gespräch führt ihr."
        ),
    ),
    Spiel(
        id="anlaute",
        nummer=12,
        phase=4,
        titel="Anlaute",
        alter="ab 4 Jahren",
        ablauf=(
            "Das Gerät fragt: „Was fängt an wie Mmmaus?“ Auf dem Tisch liegen zum Beispiel "
            "Maus, Mond und Ball. Sie legt die Figur auf, deren Name genauso anfängt. Ein "
            "„falsch“ gibt es auch hier nicht, nur ein freundliches Nachsprechen beider Wörter."
        ),
        foerdert=(
            "Hören, aus welchen Lauten ein Wort besteht. Das ist die wichtigste Vorstufe zum Lesen."
        ),
        warum=(
            "Bevor ein Kind lesen lernt, muss es hören, dass „Maus“ und „Mond“ gleich "
            "anfangen. Forscher nennen das phonologische Bewusstheit. In Würzburg haben "
            "Petra Küspert und Wolfgang Schneider dafür das Programm „Hören, lauschen, "
            "lernen“ entwickelt. Kinder, die im letzten Kindergartenjahr täglich solche "
            "Lautspiele machten, lernten in der Schule leichter lesen und schreiben. Am "
            "meisten half es den Kindern, die es sonst schwer gehabt hätten."
        ),
    ),
)


def spiel(kennung: str) -> Spiel | None:
    return next((s for s in SPIELE if s.id == kennung), None)
