all:
	musixtex -l -p main.tex
	biber main
	musixtex -l -p main.tex
	cp main.pdf out.pdf

single:
	musixtex -l -p singleDev.tex
	cp singleDev.pdf out.pdf

midis:
	python3 midify.py content

clean:
	rm -rf main.pdf main.aux singleDev.pdf singleDev.aux main.toc missfont.log musixtex.log *.idx *.ilg *.ind main.out singleDev.out *.bbl *.bcf *.blg main.run.xml singleDev.run.xml midiOutput comment.cut