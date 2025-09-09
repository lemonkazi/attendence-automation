# Use an official Node.js runtime as a parent image
FROM node:18-alpine

# Set the working directory
WORKDIR /usr/src/app

# Copy package.json and yarn.lock
COPY package.json yarn.lock ./

# Install dependencies
RUN yarn install

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5173

# Command to run the app
CMD ["yarn", "dev"]
