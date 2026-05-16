from app.composition_root import create_app
import config

app = create_app(config)

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
