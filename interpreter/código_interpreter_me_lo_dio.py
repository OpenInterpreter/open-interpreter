import random

def generate_surreal_poem():
       surreal_words = ['sueño', 'mariposa', 'espejo', 'laberinto', 'fantasma', 'cascada', 'eco', 'nube', 'reloj', 'sombras']

       # Generate random combinations of words
       combinations = random.sample(surreal_words, k=3)

       # Create stanzas
       stanzas = []
       for combination in combinations:
           stanza = f'I wander through the {combination}\nLike a {combination} lost in time\n'
           stanzas.append(stanza)

       # Add programming elements
       programming_metaphor = random.choice(['cadenas de código', 'bucles infinitos', 'variables misteriosas'])
       programming_line = f'With {programming_metaphor} that intertwine\n'

       # Combine stanzas and programming line
       poem = '\n'.join(stanzas) + programming_line

       return poem

surreal_poem = generate_surreal_poem()
print(surreal_poem)