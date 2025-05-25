import streamlit as st
import pickle
import pandas as pd
import requests
from googleapiclient.discovery import build


def fetch_poster(movie_id):
    response = requests.get(
        f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US')
    data = response.json()
    return "https://image.tmdb.org/t/p/w500/" + data['poster_path']


def fetch_imdb_info(movie_id):
    # Get TMDB movie details including IMDb ID
    response = requests.get(
        f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US')
    data = response.json()

    imdb_id = data.get('imdb_id')
    if not imdb_id:
        return None, None

    # Get IMDb rating from OMDb API (using IMDb ID)
    omdb_api_key = "92d15a35"  # OMDb API key
    omdb_response = requests.get(f'http://www.omdbapi.com/?i={imdb_id}&apikey={omdb_api_key}')
    omdb_data = omdb_response.json()

    imdb_rating = omdb_data.get('imdbRating', 'N/A')
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/"

    return imdb_rating, imdb_url


def fetch_trailer(movie_title):
    try:
        # YouTube API setup
        youtube_api_key = "AIzaSyDceDrR7EcwVpMFnxambohTPVzCprvBHss"  # YouTube API key
        youtube = build("youtube", "v3", developerKey=youtube_api_key)

        # First, use TMDB API to get movie ID first
        search_response = requests.get(
            f'https://api.themoviedb.org/3/search/movie?api_key=8265bd1679663a7ea12ac168da84d2e8&query={movie_title}')
        search_data = search_response.json()

        # Initialize variables
        production_companies = []
        movie_id = None
        year = ""

        # Add a better fallback URL in case everything fails
        fallback_url = f"https://www.youtube.com/results?search_query={movie_title.replace(' ', '+')}+official+trailer"

        if not search_data.get('results'):
            return fallback_url

        movie_details = search_data['results'][0]
        movie_id = movie_details['id']

        # Get year for better YouTube search
        if 'release_date' in movie_details and movie_details['release_date']:
            year = movie_details['release_date'][:4]

        # Get movie details to find production companies
        details_response = requests.get(
            f'https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8')
        details_data = details_response.json()

        # Get production company names for later comparison
        production_companies = [company['name'].lower() for company in details_data.get('production_companies', [])]

        # Try TMDB videos method first
        videos_response = requests.get(
            f'https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key=8265bd1679663a7ea12ac168da84d2e8')
        videos_data = videos_response.json()
        videos = videos_data.get('results', [])

        # Function to score trailer quality
        def score_video(video):
            score = 0

            # Check if it's an official trailer
            if video.get('type', '').lower() == 'trailer':
                score += 10

            # Check if "official" is in the name
            if 'official' in video.get('name', '').lower():
                score += 5

            # Check if it's from an official source
            if any(company in video.get('name', '').lower() for company in production_companies):
                score += 20

            # Prefer high quality
            if video.get('size', 0) >= 1080:
                score += 3

            return score

        # Sort videos by score
        if videos:
            youtube_videos = [v for v in videos if v.get('site') == 'YouTube']

            # Filter for trailers first
            trailers = [v for v in youtube_videos if v.get('type', '').lower() == 'trailer']

            if trailers:
                # Sort trailers by our custom scoring
                sorted_trailers = sorted(trailers, key=score_video, reverse=True)
                return f"https://www.youtube.com/watch?v={sorted_trailers[0]['key']}"
            elif youtube_videos:
                # If no trailers, use any YouTube video
                sorted_videos = sorted(youtube_videos, key=score_video, reverse=True)
                return f"https://www.youtube.com/watch?v={sorted_videos[0]['key']}"

        # If TMDB method didn't work, try with YouTube API directly
        # Improved search term for better results
        search_term = f"{movie_title} {year} official trailer"

        # Add studio name if available to improve search
        if production_companies and len(production_companies) > 0:
            top_company = production_companies[0]
            # Don't add generic production company names that might confuse search
            if len(top_company) > 3 and top_company not in ["the", "productions", "films", "pictures", "entertainment"]:
                search_term += f" {top_company}"

        # Search YouTube API with refined parameters
        search_response = youtube.search().list(
            q=search_term,
            part="id,snippet",
            maxResults=10,
            type="video",
            videoDefinition="high",  # Prefer HD videos
            relevanceLanguage="en"  # Prefer English results
        ).execute()

        videos = []
        for item in search_response.get("items", []):
            if "id" in item and "videoId" in item["id"]:
                # Get additional details about the video
                video_response = youtube.videos().list(
                    part="contentDetails,statistics,snippet",
                    id=item["id"]["videoId"]
                ).execute()

                if video_response.get("items"):
                    video_data = video_response["items"][0]

                    # Score the video based on quality factors
                    score = 0

                    # Check title for relevance and improve matching
                    title = video_data["snippet"]["title"].lower()

                    # Strong indicators of official trailers
                    if movie_title.lower() in title:
                        score += 15
                    if "trailer" in title:
                        score += 10
                    if "official" in title:
                        score += 8
                    if year in title:
                        score += 5

                    # Negative indicators
                    if "reaction" in title or "review" in title:
                        score -= 10
                    if "fan made" in title or "fanmade" in title:
                        score -= 15

                    # Check channel name for official sources
                    channel = video_data["snippet"]["channelTitle"].lower()

                    # Known movie studios
                    studios = ["disney", "warner", "universal", "paramount", "sony", "columbia",
                               "fox", "mgm", "lionsgate", "dreamworks", "pixar", "marvel",
                               "lucasfilm", "20th century", "netflix", "amazon", "a24"]

                    # Production company match is a strong indicator
                    if production_companies and any(company in channel for company in production_companies):
                        score += 25
                    elif any(studio in channel for studio in studios):
                        score += 20

                    # Check view count (popularity)
                    views = int(video_data["statistics"].get("viewCount", 0))
                    score += min(views // 100000, 15)  # Cap at 15 points

                    # Add to videos list with score
                    videos.append({
                        "id": item["id"]["videoId"],
                        "title": video_data["snippet"]["title"],
                        "score": score,
                        "views": views,
                        "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    })

        # Sort videos by score
        sorted_videos = sorted(videos, key=lambda x: x["score"], reverse=True)

        if sorted_videos:
            return sorted_videos[0]["url"]

        return fallback_url

    except Exception as e:
        # If any error occurs, fall back to a simple search URL
        st.error(f"Error fetching trailer: {str(e)}")
        return f"https://www.youtube.com/results?search_query={movie_title.replace(' ', '+')}+official+trailer"


def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]
    recommended_movies = []
    recommended_movies_posters = []
    recommended_movies_trailers = []
    recommended_movies_imdb_ratings = []
    recommended_movies_imdb_urls = []

    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        movie_title = movies.iloc[i[0]].title

        recommended_movies.append(movie_title)
        recommended_movies_posters.append(fetch_poster(movie_id))
        recommended_movies_trailers.append(fetch_trailer(movie_title))

        # Get IMDb rating and URL
        imdb_rating, imdb_url = fetch_imdb_info(movie_id)
        recommended_movies_imdb_ratings.append(imdb_rating)
        recommended_movies_imdb_urls.append(imdb_url)

    return recommended_movies, recommended_movies_posters, recommended_movies_trailers, recommended_movies_imdb_ratings, recommended_movies_imdb_urls


# Load data
movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

# Set page layout
st.set_page_config(page_title="Movie Recommender", layout="wide")

# Add Font Awesome for YouTube icon and IMDb icon
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">',
    unsafe_allow_html=True)

# Custom CSS to remove black boxes and add IMDb icon styling
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), 
                    url('https://wallpaperaccess.com/full/3295833.jpg') no-repeat center center fixed;
        background-size: cover;
    }

    section.main > div, .stHorizontalBlock, .css-1d391kg, .css-12oz5g7,
    .selector-container, .recommend-section, .movie-card {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    .main-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 42px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 10px;
        color: #ffffff;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        letter-spacing: 1px;
    }

    .subheading {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 22px;
        font-weight: 400;
        text-align: center;
        color: #e6e6e6;
        margin-bottom: 30px;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.4);
    }

    .movie-title {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 16px;
        font-weight: 600;
        text-align: center;
        padding: 10px 8px;
        color: #ffffff;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .movie-rating {
        text-align: center;
        color: #ffd700;
        font-weight: 600;
        margin-top: 5px;
        margin-bottom: 10px;
        font-size: 16px;
        text-shadow: 0 0 3px rgba(255, 215, 0, 0.6);
    }

    .movie-links {
        display: flex;
        justify-content: center;
        gap: 15px;
        margin-bottom: 15px;
    }

    .trailer-link, .imdb-link {
        text-align: center;
    }

    .youtube-icon {
        color: #FF0000;
        font-size: 28px;
        filter: drop-shadow(0 0 5px rgba(255, 0, 0, 0.7));
        transition: all 0.3s ease;
        opacity: 0.9;
    }

    .youtube-icon:hover {
        filter: drop-shadow(0 0 8px rgba(255, 0, 0, 1));
        transform: scale(1.1);
        opacity: 1;
    }

    .imdb-icon {
        color: #f5de50;
        font-size: 28px;
        filter: drop-shadow(0 0 5px rgba(245, 222, 80, 0.7));
        transition: all 0.3s ease;
        opacity: 0.9;
        background-color: #000000;
        padding: 2px 4px;
        border-radius: 4px;
        font-weight: bold;
        font-family: 'Arial Black', sans-serif;
        display: inline-block;
        /* Added these properties to match YouTube icon dimensions */
        line-height: 28px;
        height: 28px;
    }

    .imdb-icon:hover {
        filter: drop-shadow(0 0 8px rgba(245, 222, 80, 1));
        transform: scale(1.1);
        opacity: 1;
    }

    .stButton > button {
        background-color: #E50914 !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 12px 24px !important;
        font-size: 18px !important;
        border-radius: 6px !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(229, 9, 20, 0.5) !important;
        transition: all 0.3s !important;
        width: 100%;
    }

    .stButton > button:hover {
        background-color: #F40612 !important;
        box-shadow: 0 6px 16px rgba(229, 9, 20, 0.6) !important;
        transform: translateY(-2px) !important;
    }

    .footer {
        text-align: center;
        margin-top: 40px;
        padding: 20px;
        color: #a0a0a0;
        font-size: 14px;
        background-color: transparent !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# App title and subheading
st.markdown('<h1 class="main-header">🎬 Cine Match </h1>', unsafe_allow_html=True)
st.markdown('<div class="subheading">Find your next favourite movie based on what you love! 🍿</div>',
            unsafe_allow_html=True)

# Movie selection
selected_movie_name = st.selectbox(
    'Select a movie you enjoyed:',
    movies['title'].values
)

# Button for recommendations
if st.button('🔍 Get Recommendations'):
    # Show loading indicator
    with st.spinner('Finding perfect matches for you...'):
        names, posters, trailers, imdb_ratings, imdb_urls = recommend(selected_movie_name)

    st.markdown(
        f'<div class="recommendations-header">Because you liked "{selected_movie_name}", you might enjoy:</div>',
        unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.image(posters[0], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[0]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="movie-rating">⭐ {imdb_ratings[0]}/10</div>', unsafe_allow_html=True)
        st.markdown(
            f'''<div class="movie-links">
                    <div class="trailer-link"><a href="{trailers[0]}" target="_blank"><i class="fab fa-youtube youtube-icon"></i></a></div>
                    <div class="imdb-link"><a href="{imdb_urls[0]}" target="_blank"><span class="imdb-icon">IMDb</span></a></div>
                </div>''',
            unsafe_allow_html=True)

    with col2:
        st.image(posters[1], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[1]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="movie-rating">⭐ {imdb_ratings[1]}/10</div>', unsafe_allow_html=True)
        st.markdown(
            f'''<div class="movie-links">
                    <div class="trailer-link"><a href="{trailers[1]}" target="_blank"><i class="fab fa-youtube youtube-icon"></i></a></div>
                    <div class="imdb-link"><a href="{imdb_urls[1]}" target="_blank"><span class="imdb-icon">IMDb</span></a></div>
                </div>''',
            unsafe_allow_html=True)

    with col3:
        st.image(posters[2], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[2]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="movie-rating">⭐ {imdb_ratings[2]}/10</div>', unsafe_allow_html=True)
        st.markdown(
            f'''<div class="movie-links">
                    <div class="trailer-link"><a href="{trailers[2]}" target="_blank"><i class="fab fa-youtube youtube-icon"></i></a></div>
                    <div class="imdb-link"><a href="{imdb_urls[2]}" target="_blank"><span class="imdb-icon">IMDb</span></a></div>
                </div>''',
            unsafe_allow_html=True)

    with col4:
        st.image(posters[3], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[3]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="movie-rating">⭐ {imdb_ratings[3]}/10</div>', unsafe_allow_html=True)
        st.markdown(
            f'''<div class="movie-links">
                    <div class="trailer-link"><a href="{trailers[3]}" target="_blank"><i class="fab fa-youtube youtube-icon"></i></a></div>
                    <div class="imdb-link"><a href="{imdb_urls[3]}" target="_blank"><span class="imdb-icon">IMDb</span></a></div>
                </div>''',
            unsafe_allow_html=True)

    with col5:
        st.image(posters[4], use_container_width=True)
        st.markdown(f'<div class="movie-title">{names[4]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="movie-rating">⭐ {imdb_ratings[4]}/10</div>', unsafe_allow_html=True)
        st.markdown(
            f'''<div class="movie-links">
                    <div class="trailer-link"><a href="{trailers[4]}" target="_blank"><i class="fab fa-youtube youtube-icon"></i></a></div>
                    <div class="imdb-link"><a href="{imdb_urls[4]}" target="_blank"><span class="imdb-icon">IMDb</span></a></div>
                </div>''',
            unsafe_allow_html=True)

# Footer
st.markdown('<div class="footer">© 2025 Cine Match </div>', unsafe_allow_html=True)


