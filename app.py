import streamlit as st
import pickle
import pandas as pd
import requests


def fetch_poster(movie_id):
    response = requests.get(
        f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US')
    data = response.json()
    return "https://image.tmdb.org/t/p/w500/" + data['poster_path']


def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]
    recommended_movies = []
    recommended_movies_posters = []
    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        recommended_movies.append(movies.iloc[i[0]].title)
        recommended_movies_posters.append(fetch_poster(movie_id))
    return recommended_movies, recommended_movies_posters


# Load data
movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

# Set page layout
st.set_page_config(page_title="Movie Recommender", layout="wide")

# Custom CSS for better styling
st.markdown(
    """
    <style>
    body {
        background-color: #0f0f0f;
        color: #ffcc00;
    }
    .stApp {
        background: url('https://wallpaperaccess.com/full/3295833.jpg') no-repeat center center fixed;
        background-size: cover;
    }
    .movie-title {
        font-size: 18px;
        font-weight: bold;
        text-align: center;
        margin-top: 10px;
        color: #ffcc00;
    }
    .recommend-section {
        background-color: rgba(0, 0, 0, 0.7);
        padding: 20px;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title('🎬 Movie Recommender System')
st.markdown("Find your next favorite movie based on what you love! 🍿")

selected_movie_name = st.selectbox(
    'Which movie do you like?',
    movies['title'].values
)

if st.button('🔍 Recommend'):
    names, posters = recommend(selected_movie_name)

    st.markdown('<div class="recommend-section">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.image(posters[0], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[0]}</div>', unsafe_allow_html=True)
    with col2:
        st.image(posters[1], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[1]}</div>', unsafe_allow_html=True)
    with col3:
        st.image(posters[2], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[2]}</div>', unsafe_allow_html=True)
    with col4:
        st.image(posters[3], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[3]}</div>', unsafe_allow_html=True)
    with col5:
        st.image(posters[4], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[4]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

